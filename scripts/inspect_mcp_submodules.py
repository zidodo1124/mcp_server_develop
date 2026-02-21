import importlib, inspect, json
modules = ['mcp.client.sse','mcp.client.stdio','mcp.client.session','mcp.client.session_group','mcp.client.streamable_http']
info = {}
for modname in modules:
    try:
        mod = importlib.import_module(modname)
    except Exception as e:
        info[modname] = {'error': str(e)}
        continue
    members = []
    for name in dir(mod):
        if name.startswith('_'):
            continue
        try:
            obj = getattr(mod, name)
        except Exception as e:
            members.append({'name': name, 'error': str(e)})
            continue
        entry = {'name': name, 'type': type(obj).__name__}
        if inspect.isclass(obj):
            try:
                entry['signature'] = str(inspect.signature(obj))
            except Exception:
                entry['signature'] = None
            methods = []
            for m in dir(obj):
                if m.startswith('_'): continue
                try:
                    attr = getattr(obj, m)
                    if inspect.isfunction(attr) or inspect.ismethod(attr):
                        try:
                            methods.append({'name': m, 'signature': str(inspect.signature(attr))})
                        except Exception:
                            methods.append({'name': m, 'signature': None})
                except Exception:
                    continue
            entry['methods'] = methods[:100]
        elif inspect.isfunction(obj) or inspect.ismethod(obj):
            try:
                entry['signature'] = str(inspect.signature(obj))
            except Exception:
                entry['signature'] = None
        members.append(entry)
    info[modname] = {'file': getattr(mod,'__file__',None), 'members': members}
print(json.dumps(info, ensure_ascii=False, indent=2))
