from enum import Enum, unique

@unique
class RenderStyles(Enum):
    """Available render styles."""
    Filled        = "Filled"
    FilledNoEdges = "Filled (No Edges)"
    Wireframe     = "Wireframe"
