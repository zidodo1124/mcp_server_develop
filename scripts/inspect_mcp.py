import importlib

try:
    mcp = importlib.import_module('mcp')
    print('mcp', getattr(mcp, '__file__', None))
    print('members', [n for n in dir(mcp) if not n.startswith('_')])
except Exception as e:
    print('mcp import error', e)

try:
    import mcp.server as srv
    print('mcp.server members', [n for n in dir(srv) if not n.startswith('_')][:200])
except Exception as e:
    print('mcp.server import error', e)

try:
    import mcp.client as cli
    print('mcp.client members', [n for n in dir(cli) if not n.startswith('_')])
except Exception as e:
    print('mcp.client import error', e)
