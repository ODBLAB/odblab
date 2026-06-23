from vtkmodules.vtkCommonDataModel import VTK_TRIANGLE, VTK_QUAD, VTK_TETRA, VTK_PYRAMID, VTK_WEDGE, VTK_HEXAHEDRON, \
    VTK_QUADRATIC_TRIANGLE, VTK_QUADRATIC_QUAD, VTK_QUADRATIC_TETRA, VTK_QUADRATIC_PYRAMID, VTK_QUADRATIC_WEDGE, \
    VTK_QUADRATIC_HEXAHEDRON, VTK_EMPTY_CELL

_MAPPINGS: dict[str, dict[int, list[str]]] = {
    "abaqus": {
        # first-order, linear
        VTK_TRIANGLE:   ["CPS3", "CPE3", "CAX3"],
        VTK_QUAD:       ["CPS4", "CPE4", "CAX4"],
        VTK_TETRA:      ["C3D4"],
        VTK_PYRAMID:    ["C3D5"],
        VTK_WEDGE:      ["C3D6"],
        VTK_HEXAHEDRON: ["C3D8"],
        # second-order, quadratic
        VTK_QUADRATIC_TRIANGLE:   ["CPS6", "CPE6", "CAX6"],
        VTK_QUADRATIC_QUAD:       ["CPS8", "CPE8", "CAX8"],
        VTK_QUADRATIC_TETRA:      ["C3D10"],
        VTK_QUADRATIC_PYRAMID:    ["C3D13"],
        VTK_QUADRATIC_WEDGE:      ["C3D15"],
        VTK_QUADRATIC_HEXAHEDRON: ["C3D20"],
    }
}

_OPTIMIZED_MAPPINGS: dict[str, list[tuple[str, int]]] = {
    solver: sorted(
        ((element, cellType) for cellType, elements in mapping.items() for element in elements),
        key=lambda x: len(x[0]), reverse=True
    )
    for solver, mapping in _MAPPINGS.items()
}

def getCellType(elementType: str) -> int:
    """Returns the corresponding VTK cell type."""
    elementType = elementType.strip().upper()
    for mapping in _OPTIMIZED_MAPPINGS.values():
        for baseElementType, cellType in mapping:
            if baseElementType in elementType:
                return cellType
    return VTK_EMPTY_CELL
