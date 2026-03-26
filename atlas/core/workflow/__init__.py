"""Atlas workflow engine — registry, base classes, and lifecycle.

TODO: Implement after scaffolding is approved.
Components:
- BaseWorkflow abstract class
- WorkflowRegistry — discover and manage workflow modules
- AgentRegistry — register watcher/actor/interpreter agents
- Workflow lifecycle hooks (init, trigger, process, approve, act, close)
- Workflow metadata (id, name, category, trust_level, required_credentials)
- Watcher interface — observe sources for signals
- Actor interface — execute approved actions
- Interpreter interface — parse and classify signals
"""
