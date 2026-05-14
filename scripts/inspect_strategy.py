import importlib
m = importlib.import_module('app.services.strategy')
print('module TEST_MODE=', getattr(m, 'TEST_MODE', None))
from inspect import signature
print('StrategyService __init__ sig:', signature(m.StrategyService.__init__))
print('StrategyService has TEST_MODE attribute on class?', hasattr(m.StrategyService, 'TEST_MODE'))
