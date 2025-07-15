# CPU Plugins

Module quản lý CPU cho mining_environment, cung cấp các tính năng tối ưu hóa và che giấu.

## Cấu trúc thư mục

```
cpu_plugins/
├── core/                  # Chức năng cốt lõi
│   ├── __init__.py
│   ├── interfaces.py      # Định nghĩa giao diện plugin
│   ├── config.py          # Đơn giản hóa từ config_loader.py
│   └── registry.py        # Quản lý plugin
│
├── optimization/          # Tối ưu hóa CPU
│   ├── __init__.py
│   ├── amd_optimizations.py # Plugin tối ưu cho CPU AMD
│   ├── intel_cat_plugin.py  # Plugin Intel CAT
│   ├── randomx_opt_plugin.py # Plugin tối ưu RandomX
│   ├── randomx_optimizer.py # Trình tối ưu RandomX
│   └── rdt_cache_control/   # Điều khiển cache RDT
│
├── cloaking/              # Che giấu CPU
│   ├── __init__.py
│   ├── stealth_exec.py    # Thư viện che giấu quá trình
│   ├── stealth_plugin.py  # Plugin che giấu CPU
│   └── adaptive_cloak_plugin.py # Plugin che giấu thích ứng
│
├── monitoring/            # Giám sát
│   ├── __init__.py
│   ├── watchdog.py        # Giám sát trạng thái plugin
│   ├── health_probe.py    # Kiểm tra sức khỏe plugin
│   └── prometheus_exporter.py # Xuất metrics cho Prometheus
│
├── utils/                 # Tiện ích
│   ├── __init__.py
│   ├── hardware.py        # Phát hiện phần cứng
│   └── retry.py           # Cơ chế thử lại
│
├── native/                # Mã native (tùy chọn)
│   └── __init__.py
│
├── tests/                 # Kiểm thử
│   ├── __init__.py
│   ├── test_core_functionality.py
│   └── test_plugin_system.py
│
├── __init__.py            # API chính
├── requirements.txt       # Phụ thuộc
└── README.md              # Tài liệu
```

## Cài đặt

```bash
pip install -r requirements.txt
```

## Sử dụng

### Cách sử dụng cơ bản

```python
from mining_environment.cpu_plugins import PluginRegistry
from mining_environment.cpu_plugins.core import ICpuTechnique
from pathlib import Path

# Khởi tạo registry
registry = PluginRegistry.get_instance()

# Tải cấu hình
registry.load_config(Path("config/cpu_plugins.yml"))

# Khởi tạo engine (đối tượng quản lý tài nguyên)
engine = YourEngineClass()
registry.register_engine(engine)

# Khởi tạo tất cả plugins
registry.initialize_plugins()

# Lấy plugin theo tên
adaptive_cloak = registry.get_plugin("adaptive_cloak")

# Áp dụng plugin cho một tiến trình
if adaptive_cloak:
    adaptive_cloak.apply(12345)  # PID của tiến trình cần áp dụng

# Hoặc áp dụng tất cả plugins
for plugin in registry.get_all_plugins():
    plugin.apply(12345)

# Dừng tất cả plugins khi hoàn tất
registry.stop_all_plugins()
```

### Sử dụng Registry Pattern

Registry Pattern là mẫu thiết kế quản lý tập trung các đối tượng, giúp:
- Quản lý vòng đời của plugins
- Tự động khám phá và đăng ký plugins
- Cung cấp truy cập đến engine và cấu hình
- Xử lý phụ thuộc giữa các plugins

```python
from mining_environment.cpu_plugins import PluginRegistry

# Lấy instance của registry (singleton)
registry = PluginRegistry.get_instance()

# Đăng ký engine
registry.register_engine(your_engine)

# Đăng ký cấu hình
registry.register_config("plugin_name", {"option": "value"})

# Lấy plugin theo tên
plugin = registry.get_plugin("plugin_name")

# Lấy tất cả plugins theo thứ tự ưu tiên
plugins = registry.get_all_plugins()

# Lấy engine đã đăng ký
engine = registry.get_engine()

# Lấy cấu hình của plugin
config = registry.get_plugin_config("plugin_name")
```

## Tạo plugin mới

```python
from mining_environment.cpu_plugins.core import ICpuTechnique, register_plugin

@register_plugin("my_plugin")
class MyPlugin(ICpuTechnique):
    """Plugin tùy chỉnh."""
    
    # Thuộc tính bắt buộc
    name = "my_plugin"
    priority = 50  # Số thấp hơn = ưu tiên cao hơn
    
    def __init__(self):
        """Khởi tạo plugin."""
        self.logger = logging.getLogger(__name__)
        self._tracked_pids = set()
    
    def init(self, engine, config=None):
        """
        Khởi tạo plugin với engine và cấu hình.
        
        Args:
            engine: Engine quản lý tài nguyên
            config: Cấu hình tùy chọn
            
        Returns:
            True nếu khởi tạo thành công, False nếu thất bại
        """
        self.engine = engine
        self.config = config or {}
        
        try:
            # Khởi tạo plugin
            self.logger.info("Plugin đã khởi tạo")
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khởi tạo plugin: {e}")
            return False
    
    def apply(self, pid):
        """
        Áp dụng plugin cho một PID.
        
        Args:
            pid: Process ID cần áp dụng
            
        Returns:
            True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            # Thực hiện tác vụ với PID
            self._tracked_pids.add(pid)
            self.logger.debug(f"Đã áp dụng plugin cho PID={pid}")
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi áp dụng plugin cho PID={pid}: {e}")
            return False
    
    def stop(self):
        """
        Dừng plugin và giải phóng tài nguyên.
        
        Returns:
            True nếu dừng thành công, False nếu thất bại
        """
        try:
            # Giải phóng tài nguyên
            self._tracked_pids.clear()
            self.logger.info("Plugin đã dừng")
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi dừng plugin: {e}")
            return False
```

## Các thay đổi trong phiên bản mới

1. **Cấu trúc thư mục**:
   - Tổ chức theo miền chức năng: core, optimization, cloaking, monitoring, utils
   - Mỗi miền chức năng có thể mở rộng độc lập

2. **Registry Pattern**:
   - Quản lý tập trung các plugins thông qua `PluginRegistry`
   - Đơn giản hóa việc truy cập và quản lý vòng đời plugin

3. **Giao diện Plugin**:
   - Các phương thức trả về `bool` để chỉ báo trạng thái thành công/thất bại
   - Docstrings và type hints đầy đủ
   - Cải thiện xử lý lỗi

4. **Đăng ký Plugin**:
   - Sử dụng decorator `@register_plugin("plugin_name")` với tên plugin bắt buộc
   - Loại bỏ factory pattern, đơn giản hóa việc tạo plugin mới 