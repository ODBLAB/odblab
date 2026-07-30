%-----------------------------------------------------------------------------------------------------------------------
% Official MATLAB wrapper for the ODBLAB Python package.
% https://github.com/ODBLAB/odblab
%-----------------------------------------------------------------------------------------------------------------------
% Copyright (c) 2026, Carlos Souto and Diego Salamanca
% Contact: csouto@fe.up.pt; diazsdiego@uniovi.es
% License: https://spdx.org/licenses/GPL-3.0-only.html
%-----------------------------------------------------------------------------------------------------------------------

classdef odblab < handle

    properties (Access = private, NonCopyable)
        pyObj
    end

    properties (Dependent)
        nodes
        types
        elements
        times
        nodeHeaders
        centroidHeaders
        nodeData
        centroidData
        path
    end

    methods (Static, Access = private)

        function autoInstallPythonPackage()
            env = pyenv();
            if env.Version == ""
                error("odblab:MissingPython", "Python was not detected by MATLAB. Python must first be installed.");
            end
            if py.importlib.util.find_spec("odblab") == py.None
                answer = questdlg("The 'odblab' package is not installed in the current Python environment. " + ...
                    "Install it now via 'pip'?", "Missing Python Package", "Yes", "No", "No");
                if answer == "Yes"
                    status = system("""" + env.Executable + """ -m pip install odblab", "-echo");
                    if status ~= 0, error("odblab:PipFailed", "Failed to install the 'odblab' package."); end
                else
                    error("odblab:MissingPythonPackage", ...
                        "The 'odblab' package is not installed in the current Python environment.");
                end
            end
        end

    end

    methods (Static)

        function database = load(filePath, cpus)
            arguments
                filePath {mustBeTextScalar}
                cpus (1, 1) {mustBeInteger, mustBeNonnegative} = 0
            end
            database = odblab();
            if cpus, database.pyObj = py.odblab.load(py.str(filePath), py.int(cpus));
            else,    database.pyObj = py.odblab.load(py.str(filePath));
            end
        end

        function view(database)
            arguments
                database (1, 1) odblab
            end
            py.odblab.view(database.pyObj);
        end

    end

    methods (Access = private)
        function obj = odblab()
            odblab.autoInstallPythonPackage();
        end
    end

    methods

        function nodes = get.nodes(obj)
            nodes = single(obj.pyObj.nodes);
        end

        function types = get.types(obj)
            types = string(obj.pyObj.types.tolist())';
        end

        function elements = get.elements(obj)
            validMask = ~logical(obj.pyObj.elements.mask)';
            paddedElements = int32(obj.pyObj.elements)' + 1;
            elements = mat2cell(paddedElements(validMask)', 1, sum(validMask, 1))';
        end

        function keys = nodeSetKeys(obj, index)
            arguments
                obj, index = missing
            end
            keys = string(py.list(obj.pyObj.nodeSets.keys()))';
            if nargin > 1, keys = keys(index); end
        end

        function keys = elementSetKeys(obj, index)
            arguments
                obj, index = missing
            end
            keys = string(py.list(obj.pyObj.elementSets.keys()))';
            if nargin > 1, keys = keys(index); end
        end

        function set = nodeSets(obj, key)
            arguments
                obj, key {mustBeTextScalar}
            end
            set = int32(py.operator.getitem(obj.pyObj.nodeSets, py.str(key)))' + 1;
        end

        function set = elementSets(obj, key)
            arguments
                obj, key {mustBeTextScalar}
            end
            set = int32(py.operator.getitem(obj.pyObj.elementSets, py.str(key)))' + 1;
        end

        function times = get.times(obj)
            times = single(obj.pyObj.times)';
        end

        function nodeHeaders = get.nodeHeaders(obj)
            nodeHeaders = string(obj.pyObj.nodeHeaders.tolist())';
        end

        function centroidHeaders = get.centroidHeaders(obj)
            centroidHeaders = string(obj.pyObj.centroidHeaders.tolist())';
        end

        function nodeData = get.nodeData(obj)
            nodeData = single(obj.pyObj.nodeData);
        end

        function centroidData = get.centroidData(obj)
            centroidData = single(obj.pyObj.centroidData);
        end

        function path = get.path(obj)
            path = string(obj.pyObj.path);
        end

        function disp(obj)
            repr = py.getattr(obj.pyObj, "__repr__");
            py.print(repr(py.int(1)));
        end

        function varargout = get(obj, fields, position, options)
            arguments
                obj
                fields (1, :) {mustBeText}
                position {mustBeTextScalar}
                options.region {mustBeTextScalar} = ""
                options.frames (1, :) {mustBeNumericOrLogical} = []
            end
            isSingleField = ischar(fields) || (isstring(fields) && isscalar(fields));
            kwargs = struct();
            kwargs.position = py.str(position);
            if isSingleField, kwargs.fields = py.str(fields);
            else, kwargs.fields = py.tuple(cellstr(fields));
            end
            if options.region ~= "", kwargs.region = py.str(options.region); end
            if ~isempty(options.frames), kwargs.frames = py.numpy.ravel(options.frames); end
            kwargs = namedargs2cell(kwargs);
            pyOut = obj.pyObj.get(pyargs(kwargs{:}));
            convertArray = @(npArray) single(py.numpy.ascontiguousarray(npArray));
            if isSingleField
                varargout{1} = convertArray(pyOut);
            else
                result = cellfun(convertArray, cell(pyOut), "UniformOutput", false);
                if nargout == 1, varargout{1} = result;
                else, varargout = result;
                end
            end
        end

        function add(obj, data, position, options)
            arguments
                obj
                data (1, :) cell
                position {mustBeTextScalar}
                options.region {mustBeTextScalar} = ""
                options.frames (1, :) {mustBeNumericOrLogical} = []
            end
            if mod(numel(data), 2) ~= 0
                error("odblab:ValueError", "Data cell array must contain an even number of items (key-value pairs).");
            end
            convertArray = @(mlArray) py.numpy.ascontiguousarray(mlArray).reshape(int64(size(mlArray)));
            data(2:2:end) = cellfun(convertArray, data(2:2:end), "UniformOutput", false);
            kwargs = struct();
            kwargs.data = py.dict(pyargs(data{:}));
            kwargs.position = py.str(position);
            if options.region ~= "", kwargs.region = py.str(options.region); end
            if ~isempty(options.frames), kwargs.frames = py.numpy.ravel(options.frames); end
            kwargs = namedargs2cell(kwargs);
            obj.pyObj.add(pyargs(kwargs{:}));
        end

        function save(obj)
            obj.pyObj.save()
        end

    end

end
