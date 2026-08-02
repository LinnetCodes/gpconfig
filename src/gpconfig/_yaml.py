"""Safe YAML loading helpers for gpconfig."""

from collections.abc import Hashable
from typing import Any, TextIO

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node

_YAML_MERGE_TAG = "tag:yaml.org,2002:merge"


class _RejectDuplicateKeysSafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate explicit keys in each mapping."""

    def construct_mapping(
        self, node: Node, deep: bool = False
    ) -> dict[Any, Any]:
        """Construct a mapping after rejecting duplicate explicit keys."""
        if not isinstance(node, MappingNode):
            return super().construct_mapping(node, deep=deep)

        explicit_key_nodes = [
            key_node
            for key_node, _ in node.value
            if key_node.tag != _YAML_MERGE_TAG
        ]
        self.flatten_mapping(node)

        seen: dict[Any, Node] = {}
        for key_node in explicit_key_nodes:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue
            if key in seen:
                first_key_node = seen[key]
                raise ConstructorError(
                    f"while constructing a mapping; key {key!r} first defined here",
                    first_key_node.start_mark,
                    f"found duplicate key {key!r}; repeated here",
                    key_node.start_mark,
                )
            seen[key] = key_node

        return super().construct_mapping(node, deep=deep)


def load_yaml(stream: TextIO) -> Any:
    """Load YAML safely while rejecting duplicate explicit mapping keys.

    Args:
        stream: Text stream containing one YAML document.

    Returns:
        The Python object constructed by PyYAML's safe constructors.

    Raises:
        yaml.YAMLError: If the YAML is malformed or contains duplicate explicit
            keys in one mapping.
    """
    return yaml.load(stream, Loader=_RejectDuplicateKeysSafeLoader)
