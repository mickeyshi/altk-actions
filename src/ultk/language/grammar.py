import random
import re
from collections import defaultdict
from itertools import product
from typing import Any, Callable, Generator, Iterable

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from ultk.language.language import Expression
from ultk.language.semantics import Meaning, Universe


class Rule:
    """Basic class for a grammar rule.  Grammar rules in ULTK correspond
    to functions.  One can think of a grammar as generating complex functions from
    more basic ones.

    Attributes:
        lhs: left-hand side of the rule (can be anything)
            conceptually, the output type of a function
        rhs: right-hand side; assumed to be an iterable
            conceptually, a list of types of inputs
        func: a callable, the function to be computed when a node with this rule is executed
        name: name of the function
        weight: a relative weight to assign to this rule
            when added to a grammar, all rules with the same LHS will be weighted together
    """

    def __init__(
        self,
        name: str,
        lhs: Any,
        rhs: Iterable[Any],
        func: Callable = lambda *args: None,
        weight: float = 1.0,
    ):
        self.lhs = lhs
        self.rhs = rhs
        self.func = func
        self.name = name
        self.weight = weight

    def is_terminal(self) -> bool:
        """Whether this is a terminal rule.  In our framework, this means that RHS is empty,
        i.e. there are no arguments to the function.
        """
        return self.rhs is None

    def __str__(self) -> str:
        out_str = f"{str(self.lhs)} -> {self.name}"
        if not self.is_terminal():
            out_str += f"({', '.join(str(typ) for typ in self.rhs)})"
        return out_str


class GrammaticalExpression(Expression):
    """A GrammaticalExpression has been built up from a Grammar by applying a sequence of Rules.
    Crucially, it is _callable_, using the functions corresponding to each rule.

    A GrammaticalExpression, when called, takes in a Referent.  Because of this, a Meaning can
    be generated by specifying a Universe (which contains Referents).

    Attributes:
        name: name of the top-most function
        func: the function
        children: child expressions (possibly empty)
    """

    def __init__(
        self,
        rule_name: str,
        func: Callable,
        children: Iterable,
        meaning: Meaning = None,
        form: str = None,
    ):
        super().__init__(form, meaning)
        self.rule_name = rule_name
        self.func = func
        self.children = children

    def yield_string(self) -> str:
        """Get the 'yield' string of this term, i.e. the concatenation
        of the leaf nodes.

        This is useful for thinking of a `Grammar` as generating derivation trees for
        an underlying CFG.  This method will then generate the strings generated by
        the corresponding CFG.
        """
        if self.children is None:
            return str(self)
        return "".join(child.yield_string() for child in self.children)

    def evaluate(self, universe: Universe) -> Meaning:
        # TODO: this presupposes that the expression has type Referent -> bool.  Should we generalize?
        # and that leaf nodes will take Referents as input...
        # NB: important to use `not self.meaning` and not `self.meaning is None` because of how
        # Expression.__init__ initializes an "empty" meaning if `None` is passed
        if not self.meaning:
            self.meaning = Meaning(
                [referent for referent in universe.referents if self(referent)],
                universe,
            )
        return self.meaning

    def to_dict(self) -> dict:
        the_dict = super().to_dict()
        the_dict["grammatical_expression"] = str(self)
        the_dict["length"] = len(self)
        return the_dict

    def __call__(self, *args):
        if self.children is None:
            return self.func(*args)
        return self.func(*(child(*args) for child in self.children))

    def __len__(self):
        length = 1
        if self.children is not None:
            length += sum(len(child) for child in self.children)
        return length

    def __eq__(self, other) -> bool:
        return (self.rule_name, self.form, self.func, self.children) == (
            other.rule_name,
            other.form,
            other.func,
            other.children,
        )

    def __hash__(self) -> int:
        # when self.children is None...
        children = self.children or tuple([])
        return hash((self.rule_name, self.form, self.func, tuple(children)))

    def __lt__(self, other) -> bool:
        children = self.children or tuple([])
        other_children = other.children or tuple([])
        return (self.rule_name, self.form, self.func, children) < (
            other.rule_name,
            other.form,
            other.func,
            other_children,
        )

    def __str__(self):
        out_str = self.rule_name
        if self.children is not None:
            out_str += f"({', '.join(str(child) for child in self.children)})"
        return out_str


class Grammar:
    """At its core, a Grammar is a set of Rules with methods for generating GrammaticalExpressions."""

    def __init__(self, start: Any):
        # _rules: nonterminals -> list of rules
        self._rules = defaultdict(list)
        # name -> rule, for fast lookup in parsing
        self._rules_by_name = {}
        self._start = start

    def add_rule(self, rule: Rule):
        self._rules[rule.lhs].append(rule)
        if rule.name in self._rules_by_name:
            raise ValueError(
                f"Rules of a grammar must have unique names. This grammar already has a rule named {rule.name}."
            )
        self._rules_by_name[rule.name] = rule

    def parse(
        self,
        expression: str,
        opener: str = "(",
        closer: str = ")",
        delimiter: str = ",",
    ) -> GrammaticalExpression:
        """Parse a string representation of an expression of a grammar.
        Note that this is not a general-purpose parsing algorithm.  We assume that the strings are of the form
            parent_name(child1_name, ..., childn_name)
        where parent_name is the name of a rule of this grammar that has a length-n RHS, and that
        childi_name is the name of a rule for each child i.

        Args:
            expression: string in the above format

        Returns:
            the corresponding GrammaticalExpression
        """
        # see nltk.tree.Tree.fromstring for inspiration
        # tokenize string roughly by splitting at open brackets, close brackets, and delimiters
        open_re, close_re, delimit_re = (
            re.escape(opener),
            re.escape(closer),
            re.escape(delimiter),
        )
        name_pattern = f"[^{open_re}{close_re}{delimit_re}]+"
        token_regex = re.compile(
            rf"{name_pattern}{open_re}|{name_pattern}|{delimit_re}\s*|{close_re}"
        )

        # stack to store the tree being built
        stack = []

        for match in token_regex.finditer(expression):
            # strip trailing whitespace if needed
            token = match.group().strip()
            # start a new expression
            if token[-1] == opener:
                name = token[:-1]
                stack.append(
                    GrammaticalExpression(name, self._rules_by_name[name].func, [])
                )
            # finish an expression
            elif token == delimiter or token == closer:
                # finished a child expression
                # TODO: are there edge cases that distinguish delimiter from closer?
                child = stack.pop()
                stack[-1].children.append(child)
            else:
                # primitive, no children, just look up
                stack.append(
                    GrammaticalExpression(token, self._rules_by_name[token].func, None)
                )
        if len(stack) != 1:
            raise ValueError("Could not parse string {expression}")
        return stack[0]

    def generate(self, lhs: Any = None) -> GrammaticalExpression:
        """Generate an expression from a given lhs."""
        if lhs is None:
            lhs = self._start
        rules = self._rules[lhs]
        the_rule = random.choices(rules, weights=[rule.weight for rule in rules], k=1)[
            0
        ]
        children = (
            None
            if the_rule.rhs is None
            else [self.generate(child_lhs) for child_lhs in the_rule.rhs]
        )
        # if the rule is terminal, rhs will be empty, so no recursive calls to generate will be made in this comprehension
        return GrammaticalExpression(the_rule.name, the_rule.func, children)

    def enumerate(
        self,
        depth: int = 8,
        lhs: Any = None,
        unique_dict: dict[Any, GrammaticalExpression] = None,
        unique_key: Callable[[GrammaticalExpression], Any] = None,
        compare_func: Callable[
            [GrammaticalExpression, GrammaticalExpression], bool
        ] = None,
    ) -> Generator[GrammaticalExpression, None, None]:
        """Enumerate all expressions from the grammar up to a given depth from a given LHS.
        This method also can update a specified dictionary to store only unique expressions, with
        a user-specified criterion of uniqueness.

        Args:
            depth: how deep the trees should be
            lhs: left hand side to start from; defaults to the grammar's start symbol
            unique_dict: a dictionary in which to store unique Expressions
            unique_key: a function used to evaluate uniqueness
            compare_func: a comparison function, used to decide which Expression to add to the dict
                new Expressions will be added as values to `unique_dict` only if they are minimal
                among those sharing the same key (by `unique_key`) according to this func

        Yields:
            all GrammaticalExpressions up to depth
        """
        # TODO: update docstring!
        # TODO: package uniqueness stuff in one dict arg?
        if lhs is None:
            lhs = self._start
        for num in range(depth):
            for expr in self.enumerate_at_depth(
                num,
                lhs,
                unique_dict=unique_dict,
                unique_key=unique_key,
                compare_func=compare_func,
            ):
                yield expr

    def enumerate_at_depth(
        self,
        depth: int,
        lhs: Any,
        unique_dict: dict[Any, GrammaticalExpression] = None,
        unique_key: Callable[[GrammaticalExpression], Any] = None,
        compare_func: Callable[
            [GrammaticalExpression, GrammaticalExpression], bool
        ] = None,
    ) -> set[GrammaticalExpression]:
        """Enumerate GrammaticalExpressions for this Grammar _at_ a fixed depth."""

        do_unique = unique_key is not None and compare_func is not None

        def add_unique(expression: GrammaticalExpression) -> None:
            expr_key = unique_key(expression)
            # if the current expression has not been generated yet
            # OR it is "less than" the current entry, add this one
            if expr_key not in unique_dict or compare_func(
                expression, unique_dict[expr_key]
            ):
                unique_dict[expr_key] = expression

        if depth == 0:
            for rule in self._rules[lhs]:
                if rule.is_terminal():
                    cur_expr = GrammaticalExpression(rule.name, rule.func, None)
                    if do_unique:
                        add_unique(cur_expr)
                    yield cur_expr

        for rule in self._rules[lhs]:
            # can't use terminal rules when depth > 0
            if rule.is_terminal():
                continue

            # get lists of possible depths for each child
            for child_depths in product(range(depth), repeat=len(rule.rhs)):
                if max(child_depths) < depth - 1:
                    continue
                # get all possible children of the relevant depths
                children_iter = product(
                    *[
                        self.enumerate_at_depth(child_depth, child_lhs)
                        for child_depth, child_lhs in zip(child_depths, rule.rhs)
                    ]
                )
                for children in children_iter:
                    cur_expr = GrammaticalExpression(rule.name, rule.func, children)
                    if do_unique:
                        add_unique(cur_expr)
                    yield cur_expr

    def get_unique_expressions(
        self,
        depth: int,
        lhs: Any = None,
        max_size: float = float("inf"),
        unique_key: Callable[[GrammaticalExpression], Any] = None,
        compare_func: Callable[
            [GrammaticalExpression, GrammaticalExpression], bool
        ] = None,
    ) -> dict[GrammaticalExpression, Any]:
        """Get all unique GrammaticalExpressions, up to a certain depth, with a user-specified criterion
        of uniqueness, and a specified comparison function for determining which Expression to save when there's a clash.
        This can be used, for instance, to measure the minimum description length of some
        Meanings, by using expression.evaluate(), which produces a Meaning for an Expression, as the
        key for determining uniqueness, and length of the expression as comparison.

        This is a wrapper around `enumerate`, but which produces the dictionary of key->Expression entries
        and returns it.  (`enumerate` is a generator with side effects).

        For Args, see the docstring for `enumerate`.

        Note: if you additionally want to store _all_ expressions, and not just the unique ones, you should
        directly use `enumerate`.

        Returns:
            dictionary of {key: GrammaticalExpression}, where the keys are generated by `unique_key`
            The GrammticalExpression which is the value will be the one that is minimum among
            `compare_func` amongst all Expressions up to `depth` which share the same key
        """
        unique_dict = {}
        # run through generator, each iteration will update unique_dict
        for _ in self.enumerate(
            depth,
            lhs=lhs,
            unique_dict=unique_dict,
            unique_key=unique_key,
            compare_func=compare_func,
        ):
            if len(unique_dict) == max_size:
                break
            pass
        return unique_dict

    def get_all_rules(self) -> list[Rule]:
        """Get all rules as a list."""
        rules = []
        for lhs in self._rules:
            rules.extend(self._rules[lhs])
        return rules

    def __str__(self):
        return "Rules:\n" + "\n".join(f"\t{rule}" for rule in self.get_all_rules())

    @classmethod
    def from_yaml(cls, filename: str):
        """Read a grammar specified in a simple YAML format.

        Expected format:

        ```
        start: bool
        rules:
        - lhs: bool
          rhs:
          - bool
          - bool
          name: "and"
          function: "lambda p1, p2 : p1 and p2"
        - lhs: bool
          rhs:
          - bool
          - bool
          name: "or"
          function: "lambda p1, p2 : p1 or p2"
        ```

        Note that for each fule, the value for `function` will be passed to
        `eval`, so be careful!

        Arguments:
            filename: file containing a grammar in the above format
        """
        with open(filename, "r") as f:
            grammar_dict = load(f, Loader=Loader)
        grammar = cls(grammar_dict["start"])
        for rule_dict in grammar_dict["rules"]:
            grammar.add_rule(
                Rule(
                    rule_dict["name"],
                    rule_dict["lhs"],
                    rule_dict["rhs"],
                    # TODO: look-up functions from a registry as well?
                    eval(rule_dict["function"]),
                )
            )
        return grammar
