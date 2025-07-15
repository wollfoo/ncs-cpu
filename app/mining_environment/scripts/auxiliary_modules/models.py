class ConfigModel:
    def __init__(self, **kwargs):
        self.processes = {'CPU': 'ml-inference', 'GPU': 'inference-cuda'}
        self.network_interface = 'eth0'
        self.process_priority_map = {'ml-inference': 2, 'inference-cuda': 3}
        self.cloak_strategies = {'enabled_strategies': ['cpu_cloaking', 'gpu_cloaking']}
        for key, value in kwargs.items():
            setattr(self, key, value)
    def get(self, key, default=None):
        return getattr(self, key, default)
