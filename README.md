# Pygame Frame Animation

- [中文文档](#中文文档)
- [English Document](#english-document)

# 中文文档

一个高性能、易集成的Pygame动画播放器，所有功能集成在**单个文件**中，无需复杂依赖。

## 目录
- [兼容性](#兼容性)
- [特性](#特性)
- [快速开始](#快速开始)
- [安装](#安装)
- [详细用法](#详细用法)
- [API参考](#api参考)
- [常见问题](#常见问题)
- [贡献](#贡献)
- [支持](#支持)
- [许可证](LICENSE)

## 兼容性

- Python: 3.8+
- Pygame: 2.0+

## 特性

- **单文件设计** - 只需复制一个文件即可开始使用
- **多种播放模式** - 支持循环(loop)、单次(once)、往返(pingpong)播放
- **智能缓存** - LRU缓存管理，自动优化内存使用
- **类型安全** - 完整的类型注解，更好的开发体验
- **灵活配置** - 支持图片路径和pygame.Surface两种帧数据源
- **高性能** - 线程安全设计，适合游戏开发
- **无缝集成** - 继承自`pygame.sprite.Sprite`，与Pygame生态完美兼容

## 快速开始

### 安装
只需将 `animation.py` 文件复制到你的项目目录中！

### 示例
```python
from animation import FramePlayer, AnimationConfig
import pygame

# 初始化pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

# 创建一些动画帧（使用pygame.Surface）
frames = {}
for state in ["idle", "walk"]:
    frames[state] = []
    for i in range(4):
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        color = (255, 100 + i*40, 50) if state == "idle" else (50, 100 + i*40, 255)
        pygame.draw.circle(surf, color, (16, 16), 10 + i*2)
        frames[state].append(surf)
# 创建动画播放器
config = AnimationConfig(
    frames=frames,
    frames_times={"idle": 0.2, "walk": 0.1},
    frame_scale=(64, 64),  # 缩放尺寸
    play_mode="loop"
)

animation = FramePlayer(config)
animation.set_state("idle")

running = True
while running:
    dt = clock.tick(60) / 1000.0  # 计算帧间隔时间
    
    # 处理事件
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if animation.state == "idle":
                    animation.set_state("walk")
                elif animation.state == "walk":
                    animation.set_state("idle")
    
    # 更新动画
    animation.update_frame(dt)
    
    # 绘制
    screen.fill((0, 0, 0))
    animation.rect.center = (400, 300)  # 设置位置
    animation.draw(screen)
    
    pygame.display.flip()

# 清理资源
animation.release()
pygame.quit()
```
## API参考

### FramePlayer 主要方法

#### `update_frame(dt: float, direction: Tuple[bool, bool] = (False, False), scale: Tuple[int, int] = (0, 0), angle: float = 0.0)`
更新动画帧
- `dt`: 时间增量（秒）
- `direction`: 翻转方向 `(flip_x, flip_y)`
- `scale`: 缩放尺寸 `(width, height)`
- `angle`: 旋转角度范围为`[0, 360)`

#### `set_state(state: str, reset_frame: bool = True, keep_progress: bool = False)`
设置动画状态
- `state`: 状态名称
- `reset_frame`: 是否重置到第一帧
- `keep_progress`: 是否保持进度比例

#### `draw(surface: pygame.Surface)`
绘制到目标surface

### 属性
- `is_playing: bool` - 是否正在播放
- `rect: pygame.Rect` - 动画位置和尺寸
- `image: pygame.Surface` - 当前帧图像


## 详细用法
### 使用图片文件
```python
def load_image(path):
    return pygame.image.load(path).convert_alpha()

# 定义帧序列
frames = {
    "run": ["run_0.png", "run_1.png", "run_2.png", "run_3.png"],
    "jump": ["jump_0.png", "jump_1.png", "jump_2.png"]
}

# 创建配置
config = AnimationConfig(
    frames=frames,
    frames_times={"run": 0.1, "jump": 0.15},
    frame_scale=(48, 48)
)

# 创建动画播放器（需要提供图片资源字典）
injection = AnimationParamInjection(
    image_provider={path: load_image(path) for path in set(sum(frames.values(), []))}
)

animation = FramePlayer(config, injection)
```
### 事件回调
```python
def on_animation_complete():
    print("动画播放完成！")
    animation.set_state("idle")

def on_frame_change(frame_index):
    print(f"切换到第 {frame_index} 帧")

def on_state_change(new_state):
    print(f"状态切换到: {new_state}")

# 添加回调
animation.add_complete_callback(on_animation_complete)
animation.add_frame_change_callback(on_frame_change)
animation.add_state_change_callback(on_state_change)
```

### 播放模式控制
```python
# 设置播放模式
animation.set_play_mode("once")    # 播放一次
animation.set_play_mode("loop")    # 循环播放
animation.set_play_mode("pingpong") # 往返播放

# 控制播放
animation.pause()    # 暂停
animation.resume()   # 继续播放
animation.rewind()   # 重置到开始
```

## 参数注入配置选项
### AnimationConfig 参数
| 参数	| 类型	 | 说明	  | 默认值    |
| :--------: | :--------: | :--------: | :--------: |
| `frames` | `Dict[str, List[str, pygame.Surface]]` |	动画帧数据	|必填 |
| `frames_times` | `Dict[str, float]`	|每帧持续时间(秒)	|必填
| `frame_scale`	| `Tuple[int, int]`	|帧缩放尺寸	| `(0, 0)`|
| `play_mode`	| `Literal["loop", "once", "pingpong"]`	|播放模式	| `"loop"` |
| `max_cache_size`	| `int`	|缓存大小	| `200` |

#### 一些参数的具体说明

##### 参数`frame_scale`

设置帧的缩放尺寸，默认为 `(0, 0)`，即不缩放。

##### 参数`play_mode`模式介绍
* `"loop"` - 循环播放（0->1->2->0->1->2...）

* `"once"` - 播放一次后停止（0->1->2->结束）

* `"pingpong"` - 往返播放（0->1->2->1->0）

##### 参数`max_cache_size`

设置缓存最大容量，单位为帧数。当缓存超过最大容量时，会自动删除最早的帧。

**注：`max_cache_size` 不能小于 `10`(`_AnimationMagicNumber.CACHE_MIN_SIZE`)**

### AnimationParamInjection 参数
| 参数	| 类型	 | 说明	  | 默认值    | 提供为`None`时`FramePlayer.__init__`初始化给予的值 |
| :--------: | :--------: | :--------: | :--------: | :--------: |
| `image_provider` | `Optional[Dict[str, pygame.Surface]]` |	图片数据	| `None` | `{}` |
| `logger_instance` | `Optional[AbstractLogger]` | 日志实例 | `None` | `DefaultLogger()` |
| `state_manager` | `Optional[_FrameStateManager]` |	状态管理器	| `None` | `_FrameStateManager(args)` |
| `cache_manager` | `Optional[_FrameCacheManager]` |	缓存管理器	| `None` | `_FrameCacheManager(args)` |

## 常见问题
### Q: 为什么选择单文件设计？
A: 单文件设计使得集成更加简单，无需处理多文件依赖关系，特别适合小型到中型项目。

### Q: 如何管理内存？
A: 内置LRU缓存系统会自动管理内存使用，当缓存达到上限时会自动移除最久未使用的资源。

### Q: 支持多线程吗？
A: 是的！所有缓存操作都是线程安全的(使用了`threading.RLock()`)，可以在多线程环境中使用。

### Q: 如何释放资源？
A: 调用 `animation.release()` 或使用上下文管理器：

```python
with FramePlayer(config) as animation:
    ...
```
虽然不推荐用`__del__`或`del animation`自动销毁，但`__del__`直接调用`release()`，也可以正常释放（在没有`release()`使用`__del__`会有警告）

## 贡献
欢迎提交Issue和Pull Request！对于单文件项目，建议：

保持向后兼容性

添加详细的类型注解

在添加新功能时考虑文件大小

## 支持
如果你遇到问题：

- 查看文件内的详细注释
- 检查类型提示获取参数信息
- 提交Issue时请提供最小重现示例


## 高级用法

### 使用FramePlayerEasilyGenerator
```python
from animation import FramePlayerEasilyGenerator, AnimationConfig

# 简单创建方式
animation = FramePlayerEasilyGenerator.create(
    frames={"idle": ["idle_1.png", "idle_2.png"]},
    frames_times={"idle": 0.2}
)

# 完整参数创建方式
animation = FramePlayerEasilyGenerator.create(
    config=AnimationConfig(
        frames={"walk": ["walk_1.png", "walk_2.png"]},
        frames_times={"walk": 0.1},
        play_mode="pingpong"
    ),
    injection=AnimationParamInjection(
        logger_instance=custom_logger
    )
)
```

### 多状态动画示例
```python
# 定义多个动画状态
states = {
    "idle": ["idle_1.png", "idle_2.png", "idle_3.png"],
    "walk": ["walk_1.png", "walk_2.png", "walk_3.png", "walk_4.png"],
    "jump": ["jump_1.png", "jump_2.png"]
}

# 配置不同状态的播放速度
times = {
    "idle": 0.3,
    "walk": 0.1,
    "jump": 0.2
}

config = AnimationConfig(
    frames=states,
    frames_times=times,
    play_mode="loop"
)

animation = FramePlayer(config)

# 根据游戏逻辑切换状态
def handle_input():
    if player.is_walking():
        animation.set_state("walk")
    elif player.is_jumping():
        animation.set_state("jump")
    else:
        animation.set_state("idle")
```

## 性能优化建议
1. 对于大量动画，适当增加max_cache_size
2. 重用AnimationConfig对象创建多个动画播放器
3. 对于不常用的动画状态，可以手动调用clear_cache()
4. 使用Surface帧比图片路径加载更快

## 贡献指南
欢迎提交Issue和Pull Request！贡献时请注意：

1. 保持向后兼容性
2. 添加详细的类型注解
3. 在添加新功能时考虑文件大小
4. 遵循现有代码风格
5. 为新增功能添加测试用例
6. 更新文档和示例

## 社区规范
1. 提交Issue前请先搜索是否已有类似问题
2. 提交Pull Request时请描述清楚变更内容
3. 讨论问题时保持专业和友善
4. 遵守开源社区行为准则


# English Document

A high-performance, easy-to-integrate Pygame animation player, with all functionality integrated into a **single file**, requiring no complex dependencies.

## Table of Contents
- [Compatibility](#compatibility)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Detailed Usage](#detailed-usage)
- [API Reference](#api-reference)
- [FAQ](#faq)
- [Contributing](#contributing)
- [Support](#support)
- [License](LICENSE)

## Compatibility

- Python: 3.8+
- Pygame: 2.0+

## Features

- **Single File Design** - Just copy one file to start using
- **Multiple Playback Modes** - Supports loop, once, and pingpong playback
- **Smart Caching** - LRU cache management, automatically optimizes memory usage
- **Type Safety** - Full type annotations for a better development experience
- **Flexible Configuration** - Supports both image paths and `pygame.Surface` objects as frame data sources
- **High Performance** - Thread-safe design, suitable for game development
- **Seamless Integration** - Inherits from `pygame.sprite.Sprite`, perfectly compatible with the Pygame ecosystem

## Quick Start

### Installation
Simply copy the `animation.py` file into your project directory!

### Example
```python
from animation import FramePlayer, AnimationConfig
import pygame

# Initialize pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

# Create some animation frames (using pygame.Surface)
frames = {}
for state in ["idle", "walk"]:
    frames[state] = []
    for i in range(4):
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        color = (255, 100 + i*40, 50) if state == "idle" else (50, 100 + i*40, 255)
        pygame.draw.circle(surf, color, (16, 16), 10 + i*2)
        frames[state].append(surf)
# Create the animation player
config = AnimationConfig(
    frames=frames,
    frames_times={"idle": 0.2, "walk": 0.1},
    frame_scale=(64, 64),  # Scale size
    play_mode="loop"
)

animation = FramePlayer(config)
animation.set_state("idle")

running = True
while running:
    dt = clock.tick(60) / 1000.0  # Calculate frame delta time
    
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if animation.state == "idle":
                    animation.set_state("walk")
                elif animation.state == "walk":
                    animation.set_state("idle")
    
    # Update animation
    animation.update_frame(dt)
    
    # Draw
    screen.fill((0, 0, 0))
    animation.rect.center = (400, 300)  # Set position
    animation.draw(screen)
    
    pygame.display.flip()

# Cleanup resources
animation.release()
pygame.quit()
```
## API Reference

### FramePlayer Main Methods

#### `update_frame(dt: float, direction: Tuple[bool, bool] = (False, False), scale: Tuple[int, int] = (0, 0), angle: float = 0.0)`
Update the animation frame
- `dt`: Time delta (seconds)
- `direction`: Flip direction `(flip_x, flip_y)`
- `scale`: Scaling dimensions `(width, height)`
- `angle`: Rotation angle range `[0, 360)`

#### `set_state(state: str, reset_frame: bool = True, keep_progress: bool = False)`
Set the animation state
- `state`: State name
- `reset_frame`: Whether to reset to the first frame
- `keep_progress`: Whether to maintain progress ratio

#### `draw(surface: pygame.Surface)`
Draw to the target surface

### Properties
- `is_playing: bool` - Whether it is currently playing
- `rect: pygame.Rect` - Animation position and dimensions
- `image: pygame.Surface` - Current frame image


## Detailed Usage
### Using Image Files
```python
def load_image(path):
    return pygame.image.load(path).convert_alpha()

# Define frame sequences
frames = {
    "run": ["run_0.png", "run_1.png", "run_2.png", "run_3.png"],
    "jump": ["jump_0.png", "jump_1.png", "jump_2.png"]
}

# Create configuration
config = AnimationConfig(
    frames=frames,
    frames_times={"run": 0.1, "jump": 0.15},
    frame_scale=(48, 48)
)

# Create animation player (requires providing an image resource dictionary)
injection = AnimationParamInjection(
    image_provider={path: load_image(path) for path in set(sum(frames.values(), []))}
)

animation = FramePlayer(config, injection)
```
### Event Callbacks
```python
def on_animation_complete():
    print("Animation complete!")
    animation.set_state("idle")

def on_frame_change(frame_index):
    print(f"Switched to frame {frame_index}")

def on_state_change(new_state):
    print(f"State changed to: {new_state}")

# Add callbacks
animation.add_complete_callback(on_animation_complete)
animation.add_frame_change_callback(on_frame_change)
animation.add_state_change_callback(on_state_change)
```

### Playback Mode Control
```python
# Set playback mode
animation.set_play_mode("once")    # Play once
animation.set_play_mode("loop")    # Loop playback
animation.set_play_mode("pingpong") # Pingpong playback

# Control playback
animation.pause()    # Pause
animation.resume()   # Resume playback
animation.rewind()   # Reset to start
```

## Parameter Injection Configuration Options
### AnimationConfig Parameters
| Parameter | Type | Description | Default |
| :--------: | :--------: | :--------: | :--------: |
| `frames` | `Dict[str, List[str, pygame.Surface]]` | Animation frame data | Required |
| `frames_times` | `Dict[str, float]` | Frame duration (seconds) | Required |
| `frame_scale` | `Tuple[int, int]` | Frame scaling dimensions | `(0, 0)` |
| `play_mode` | `Literal["loop", "once", "pingpong"]` | Playback mode | `"loop"` |
| `max_cache_size` | `int` | Cache size | `200` |

#### Detailed Explanation of Some Parameters

##### Parameter `frame_scale`

Sets the scaling dimensions for frames. Default is `(0, 0)`, meaning no scaling.

##### Parameter `play_mode` Mode Introduction
* `"loop"` - Loop playback (0->1->2->0->1->2...)
* `"once"` - Play once and stop (0->1->2->end)
* `"pingpong"` - Pingpong playback (0->1->2->1->0)

##### Parameter `max_cache_size`

Sets the maximum cache capacity, measured in number of frames. When the cache exceeds the maximum capacity, the oldest frames are automatically removed.

**Note: `max_cache_size` cannot be less than `10` (`_AnimationMagicNumber.CACHE_MIN_SIZE`)**

### AnimationParamInjection Parameters
| Parameter | Type | Description | Default | Value Initialized by `FramePlayer.__init__` if Provided as `None` |
| :--------: | :--------: | :--------: | :--------: | :--------: |
| `image_provider` | `Optional[Dict[str, pygame.Surface]]` | Image data | `None` | `{}` |
| `logger_instance` | `Optional[AbstractLogger]` | Logger instance | `None` | `DefaultLogger()` |
| `state_manager` | `Optional[_FrameStateManager]` | State manager | `None` | `_FrameStateManager(args)` |
| `cache_manager` | `Optional[_FrameCacheManager]` | Cache manager | `None` | `_FrameCacheManager(args)` |

## FAQ
### Q: Why choose a single file design?
A: The single file design makes integration simpler, no need to handle multi-file dependencies, especially suitable for small to medium-sized projects.

### Q: How to manage memory?
A: The built-in LRU cache system automatically manages memory usage, removing the least recently used resources when the cache reaches its limit.

### Q: Is it multi-threaded?
A: Yes! All cache operations are thread-safe (using `threading.RLock()`), and can be used in multi-threaded environments.

### Q: How to release resources?
A: Call `animation.release()` or use the context manager:

```python
with FramePlayer(config) as animation:
    ...
```
Although not recommended to rely on `__del__` or `del animation` for automatic cleanup, `__del__` directly calls `release()`, so it can also release normally (a warning will be issued if `__del__` is used without `release()` having been called).

## Contributing
Welcome to submit Issues and Pull Requests! For a single-file project, it is recommended to:

- Maintain backward compatibility
- Add detailed type annotations
- Consider file size when adding new features

## Support
If you encounter problems:

- Check the detailed comments within the file
- Check type hints for parameter information
- Please provide a minimal reproducible example when submitting an Issue

## Advanced Usage

### Using FramePlayerEasilyGenerator
```python
from animation import FramePlayerEasilyGenerator, AnimationConfig

# Simple creation method
animation = FramePlayerEasilyGenerator.create(
    frames={"idle": ["idle_1.png", "idle_2.png"]},
    frames_times={"idle": 0.2}
)

# Full parameter creation method
animation = FramePlayerEasilyGenerator.create(
    config=AnimationConfig(
        frames={"walk": ["walk_1.png", "walk_2.png"]},
        frames_times={"walk": 0.1},
        play_mode="pingpong"
    ),
    injection=AnimationParamInjection(
        logger_instance=custom_logger
    )
)
```

### Multi-State Animation Example
```python
# Define multiple animation states
states = {
    "idle": ["idle_1.png", "idle_2.png", "idle_3.png"],
    "walk": ["walk_1.png", "walk_2.png", "walk_3.png", "walk_4.png"],
    "jump": ["jump_1.png", "jump_2.png"]
}

# Configure playback speeds for different states
times = {
    "idle": 0.3,
    "walk": 0.1,
    "jump": 0.2
}

config = AnimationConfig(
    frames=states,
    frames_times=times,
    play_mode="loop"
)

animation = FramePlayer(config)

# Switch states based on game logic
def handle_input(player):
    if player.is_walking():
        animation.set_state("walk")
    elif player.is_jumping():
        animation.set_state("jump")
    else:
        animation.set_state("idle")
```

## Performance Optimization Suggestions
1. For a large number of animations, appropriately increase `max_cache_size`
2. Reuse `AnimationConfig` objects to create multiple animation players
3. For infrequently used animation states, you can manually call `clear_cache()`
4. Using Surface frames is faster than loading from image paths

## Contribution Guidelines
Welcome to submit Issues and Pull Requests! Please note when contributing:

1. Maintain backward compatibility
2. Add detailed type annotations
3. Consider file size when adding new features
4. Follow the existing code style
5. Add test cases for new features
6. Update documentation and examples

## Community Norms
1. Please search for existing similar issues before submitting a new one
2. Clearly describe the changes when submitting a Pull Request
3. Maintain professionalism and friendliness when discussing issues
4. Adhere to the open source community code of conduct
