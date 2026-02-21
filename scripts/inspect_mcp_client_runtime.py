import importlib, inspect, json

try:
    mod = importlib.import_module('mcp.client')
except Exception as e:
    print('IMPORT_ERROR', str(e))
    raise

info = {}
info['module_file'] = getattr(mod, '__file__', None)
info['members'] = []
for name in dir(mod):
    if name.startswith('_'):
        continue
    try:
        obj = getattr(mod, name)
    except Exception as e:
        info['members'].append({'name': name, 'error': str(e)})
        continue
    entry = {'name': name, 'type': type(obj).__name__}
    if inspect.isclass(obj):
        try:
            entry['signature'] = str(inspect.signature(obj))
        except Exception:
            entry['signature'] = None
        # list callable members
        methods = []
        for m in dir(obj):
            if m.startswith('_'):
                continue
            try:
                attr = getattr(obj, m)
                if inspect.isfunction(attr) or inspect.ismethod(attr):
                    try:
                        methods.append({'name': m, 'signature': str(inspect.signature(attr))})
                    except Exception:
                        methods.append({'name': m, 'signature': None})
            except Exception:
                continue
        entry['methods'] = methods[:50]
    elif inspect.isfunction(obj) or inspect.ismethod(obj):
        try:
            entry['signature'] = str(inspect.signature(obj))
        except Exception:
            entry['signature'] = None
    info['members'].append(entry)

print(json.dumps(info, ensure_ascii=False, indent=2))
