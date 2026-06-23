from enum import Enum, unique

@unique
class Views(Enum):
    """Available viewport camera views."""
    Front     = "View Front"
    Back      = "View Back"
    Top       = "View Top"
    Bottom    = "View Bottom"
    Left      = "View Left"
    Right     = "View Right"
    Isometric = "View Isometric"
    RotateCW  = "Rotate View Clockwise"
    RotateCCW = "Rotate View Counterclockwise"
    AutoFit   = "Auto-Fit View"
