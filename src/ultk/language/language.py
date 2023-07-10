"""Classes for modeling languages as form-meaning mappings, most important among them the Language and Expression classes.

Example usage:

    >>> from ultk.language.language import Expression, Language
    >>> # assuming the meaning `a_few_meaning` has already been constructed
    >>> # define the expression
    >>> a_few = NumeralExpression(form="a few", meaning=a_few_meaning)
    >>> # define a very small language
    >>> lang_1 = Language([a_few])
    >>> # or a slightly larger one with synonymy
    >>> lang_2 = Language([a_few] * 3)
"""

import numpy as np
from ultk.language.semantics import Universe
from ultk.language.semantics import Meaning, Referent
from typing import Callable, Iterable


class Expression:

    """Minimally contains a form and a meaning."""

    def __init__(self, form: str = None, meaning: Meaning = None):
        # gneric/dummy form and meaning if not specified
        # useful for hashing in certain cases
        # (e.g. a GrammaticalExpression which has not yet been evaluate()'d and so does not yet have a Meaning)
        self.form = form or ""
        self.meaning = meaning or Meaning(tuple([]), Universe(tuple([])))

    def can_express(self, referent: Referent) -> bool:
        """Return True if the expression can express the input single meaning point and false otherwise."""
        return referent in self.meaning.referents

    def to_dict(self) -> dict:
        return {"form": self.form, "meaning": self.meaning.to_dict()}

    def __str__(self) -> str:
        return self.form
        # return f"Expression {self.form}\nMeaning:\n\t{self.meaning}"

    def __eq__(self, other: object) -> bool:
        return (self.form, self.meaning) == (other.form, other.meaning)

    def __lt__(self, other: object) -> bool:
        return (self.form, other.meaning) < (other.form, other.meaning)

    def __bool__(self) -> bool:
        return self.form and self.meaning

    def __hash__(self) -> int:
        return hash((self.form, self.meaning))


class Language:
    """Minimally contains Expression objects."""

    def __init__(self, expressions: Iterable[Expression], **kwargs):
        # Check that all expressions have the same universe
        if len(set([e.meaning.universe for e in expressions])) != 1:
            raise ValueError(
                f"All expressions must have the same meaning universe. Received universes: {[e.meaning.universe for e in expressions]}"
            )

        self.expressions = tuple(sorted(expressions))
        self.universe = expressions[0].meaning.universe

        self.__dict__.update(**kwargs)

    @property
    def expressions(self) -> tuple[Expression]:
        return self._expressions

    @expressions.setter
    def expressions(self, val: tuple[Expression]) -> None:
        if not val:
            raise ValueError("list of Expressions must not be empty.")
        self._expressions = val

    def add_expression(self, e: Expression):
        """Add an expression to the list of expressions in a language."""
        self.expressions = tuple(sorted(self.expressions + (e,)))

    def pop(self, index: int) -> Expression:
        """Removes an expression at the specified index of the list of expressions, and returns it."""
        if not len(self):
            raise Exception("Cannot pop expressions from an empty language.")
        expressions = self.expressions
        popped = expressions.pop(index)
        self.expressions = expressions
        return popped

    def is_natural(self) -> bool:
        """Whether a language represents a human natural language."""
        raise NotImplementedError

    def degree_property(self, property: Callable[[Expression], bool]) -> float:
        """Count what percentage of expressions in a language have a given property."""
        return sum([property(item) for item in self.expressions]) / len(self)

    def binary_matrix(self) -> np.ndarray:
        """Get a binary matrix of shape `(num_meanings, num_expressions)`
        specifying which expressions can express which meanings."""
        return np.array(
            [
                [float(e.can_express(m)) for e in self.expressions]
                for m in self.universe.referents
            ]
        )

    @property
    def universe(self) -> Universe:
        return self._universe

    @universe.setter
    def universe(self, val) -> None:
        self._universe = val

    def to_dict(self, **kwargs) -> dict:
        the_dict = {"expressions": [str(expr) for expr in self.expressions]}
        the_dict.update(kwargs)
        return the_dict

    def __contains__(self, expression) -> bool:
        """Whether the language has the expression"""
        return expression in self.expressions

    def __hash__(self) -> int:
        return hash(self.expressions)

    def __eq__(self, __o: object) -> bool:
        return self.expressions == __o.expressions

    def __len__(self) -> int:
        return len(self.expressions)

    def __lt__(self, other) -> bool:
        return self.expressions < other.expressions

    def __str__(self) -> str:
        return (
            "---------\nExpressions:\n"
            + "\n-----\n".join(str(expression) for expression in self.expressions)
            + "\n---------"
        )


def aggregate_expression_complexity(
    language: Language,
    expression_complexity_func: Callable[[Expression], float],
    aggregator: Callable[[Iterable[float]], float] = sum,
) -> float:
    """Aggregate complexities for individual `Expression`s into a complexity for a `Language`.

    Args:
        language: the Language to measure
        expression_complexity_func: the function that returns the complexity of an individual expression
        aggregator: (optional, default = sum) the function that aggregates individual complexities

    Returns:
        a float, the complexity of a language
    """
    return aggregator(
        expression_complexity_func(expression) for expression in language.expressions
    )
