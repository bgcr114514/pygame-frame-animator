from __future__ import annotations
from typing import (Dict, List, Tuple, NoReturn, Union, Literal, TypeAlias, Optional, Final, overload, get_args)
from collections.abc import Callable
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
import pygame

PlayMode: TypeAlias = Literal["loop", "once", "pingpong"]
Direction: TypeAlias = Tuple[bool, bool]    # (flip_x, flip_y)
Scale: TypeAlias = Tuple[int, int]    # (width, height)

FramesDict: TypeAlias = Dict[str, List[Union[str, pygame.Surface]]]
FramesTimesDict: TypeAlias = Dict[str, float]

class AbstractAnimationPlayer(ABC, pygame.sprite.Sprite):
    """animator abstract base class, define unified interface for all"""
    
    @abstractmethod
    def update_frame(self, 
                     dt: float, 
                     direction: Direction = (False, False), 
                     scale: Scale = (0, 0), 
                     angle: float = 0.0) -> None:
        """update frame"""
        pass
    
    @abstractmethod
    def set_state(self, 
                  state: str, 
                  reset_frame: bool = True, 
                  keep_progress: bool = False) -> None:
        """set animation state"""
        pass
    
    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        """draw animations"""
        pass
    
    @abstractmethod
    def add_complete_callback(self, callback: Callable) -> None:
        """add animation complete callback"""
        pass
    
    @property
    @abstractmethod
    def is_playing(self) -> bool:
        """check if animation is playing"""
        pass

class AbstractLogger(ABC):
    """logger abstract base class, define unified interface for all"""

    @abstractmethod
    def debug(self, message: str) -> None:
        """debug log"""
        pass
    
    @abstractmethod
    def info(self, message: str) -> None:
        """info log"""
        pass
    
    @abstractmethod
    def warning(self, message: str) -> None:
        """warning log"""
        pass
    
    @abstractmethod
    def error(self, message: str) -> None:
        """error log"""
        pass
    
    @abstractmethod
    def critical(self, message: str) -> None:
        """critical log"""
        pass

class DefaultLogger(AbstractLogger):
    """A concise logger implementation that only logs messages to console"""

    def debug(self, message: str) -> None:
        print(f"[DEBUG] {message}")

    def info(self, message: str) -> None:
        print(f"[INFO] {message}")

    def warning(self, message: str) -> None:
        print(f"[WARNING] {message}")

    def error(self, message: str) -> None:
        print(f"[ERROR] {message}")

    def critical(self, message: str) -> None:
        print(f"[CRITICAL] {message}")


class _AnimationMagicNumber:
    DEFAULT_MAX_CHACH_SIZE: Final[int] = 200
    ORIGINAL_IMAGE_FRAME_SCALE: Final[Scale] = (0, 0)
    DEFAULT_PLAY_MODE: Final[PlayMode] = "loop"
    CACHE_MIN_SIZE: Final[int] = 10
    SAMPLE_DISPLAY_COUNT: Final[int] = 3

    ERROR_SURFACE_SIZES: Final[Tuple[int, int]] = (32, 32)
    ERROR_RECT_COLOR: Final[Tuple[int, int, int]] = (255, 0, 0)
    
    DEBUG_FONT_SIZE: Final[int] = 16

    def __setattr__(self, name, value) -> None:
        if not hasattr(self, name):
            super().__setattr__(name, value)
            return
        raise AttributeError(f"Cannot modify immutable attribute '{name}'")
        
    
    def __delattr__(self, name) -> NoReturn:
        raise AttributeError(f"Cannot delete immutable attribute '{name}'")

@dataclass
class _CacheManagerDeps:
    max_cache_size: int
    get_scale: Callable[[], Scale]
    get_direction: Callable[[], Direction]
    process_image: Callable[[str], pygame.Surface]
    create_error_surface: Callable[[], pygame.Surface]
    surface_frames: Callable[[], bool]
    logger: AbstractLogger


class _FrameCacheManager:
    """A simple LRU cache for frame images, used by `FramePlayer` to manage frame images
    ## Thread Safety:
        This implementation uses a reentrant lock (RLock) to ensure thread safety.
        The choice of RLock over simpler Lock is intentional:
        
        1. Reentrancy Needed: Cache operations might be called through complex
           callback chains where the same thread could re-enter the cache.
        
        2. Moderate Performance: Image loading and transformation are relatively
           expensive operations, so the slight overhead of RLock is negligible
           compared to the image processing time.
        
        3. Future Optimization Ready: If profiling identifies this as a bottleneck,
           the implementation can be easily replaced with a more concurrent solution
           without changing the public interface.
    """

    __slots__ = (
        "_deps", "_cache_lock", "_image_cache", "_max_cache_size"
    )

    def __init__(self, deps: _CacheManagerDeps) -> None:
        self._cache_lock = RLock()    # Cache lock to prevent multiple threads (such as online) from accessing the cache simultaneously
        self._image_cache: OrderedDict = OrderedDict()
        self._max_cache_size = deps.max_cache_size
        self._deps = deps

    def get_cached_image(self, frame_name: str) -> pygame.Surface:
        """Retrieve processed images (thread safe with cached)
        
        Args:
            frame_name: Original image resource name
            
        Returns:
            processed pygame.Surface
            
        Raises:
            pygame.error: process image failed
            KeyError: frame name not found
            ValueError: Call this method when using Surface as a frame
        """
        if self._deps.surface_frames():
            raise ValueError(
                "This method shouldn't be called when using Surface as a frame"
            )

        cache_key = self._get_cache_key(frame_name)
        
        with self._cache_lock:
            # cache hit
            if cache_key in self._image_cache:
                self._image_cache.move_to_end(cache_key)  # update LRU cache order
                return self._image_cache[cache_key]
            
            # cache miss -> load new surface
            try:
                img = self._deps.process_image(frame_name)
                
                # evict the oldest unused cache
                if len(self._image_cache) >= self._max_cache_size:
                    self._image_cache.popitem(last=False)
                
                self._image_cache[cache_key] = img
                self._deps.logger.info(f"Cached new image: {cache_key}")
                return img
            except (pygame.error, KeyError) as errors:
                self._deps.logger.error(
                    f"Image processing failed: {frame_name} - {str(errors)}"
                )
                return self._deps.create_error_surface()
            
    def _get_cache_key(self, frame_name: str) -> Tuple[str, Tuple[int, int], Tuple[bool, bool]]:
        """Generate standardized cache keys
        Args:
            frame_name: Original image resource name

        Returns:
            An immutable tuple containing (frame name, scaling size, direction)
        """
        return frame_name, self._deps.get_scale(), self._deps.get_direction()
    
    def set_max_cache_size(self, size: int) -> None:
        if size < _AnimationMagicNumber.CACHE_MIN_SIZE:
            raise ValueError("Cache must greater than or equal to 10")
            
        with self._cache_lock:
            self._max_cache_size = size
            while len(self._image_cache) > size:
                self._image_cache.popitem(last=False)

    def clear(self) -> None:
        """Clear the cache"""
        with self._cache_lock:
            self._image_cache.clear()
        self._deps.logger.info("Cache cleared")
    
    def release(self, image: pygame.Surface) -> None:
        """Release the cache"""
        if not pygame.get_init():
            return
        
        surfaces = [image] + [
            v for v in self._image_cache.values()
            if isinstance(v, pygame.Surface)
        ]
        for surf in surfaces:
            try:
                surf.fill((0, 0, 0, 0))
            except (pygame.error, AttributeError):
                self._deps.logger.warning(f"Failed to clear surface: {surf}")
        self.clear()
    
    @property
    def lock(self) -> RLock:
        """Return the cache Rlock"""
        return self._cache_lock
    
    @property
    def max_cache_size(self) -> int:
        """Return the cache size"""
        return self._max_cache_size
    
    @property
    def image_cache(self) -> OrderedDict:
        """Return the cache dictionary"""
        return self._image_cache
    
    @property
    def info(self) -> Dict[str, Union[int, List[str]]]:
        with self.lock:
            sample_keys = list(self.image_cache.keys())[
                :_AnimationMagicNumber.SAMPLE_DISPLAY_COUNT
            ]
            return {
                "cache_size": len(self.image_cache),
                "max_size": self.max_cache_size,
                "sample_keys": sample_keys
            }

class _FrameStateManager:
    """Animation state manager, responsible for managing animation states, frame indices, 
    playback modes and callbacks.
    
    This class is designed to be used by FramePlayer to handle animation state management.
    """
    
    __slots__ = (
        "deps", "current_state", "frame_index", "time_since_last_frame",
        "play_mode", "_pingpong_direction", "_on_complete_callbacks",
        "_on_frame_change_callbacks", "_on_state_change_callbacks", "_logger",
        "frames"
    )
    
    def __init__(
        self,
        frames: FramesDict,
        logger: AbstractLogger
    ) -> None:
        self.current_state: Optional[str] = None
        self.frame_index: int = 0
        self.time_since_last_frame: float = 0
        self.play_mode: PlayMode = "loop"
        self._pingpong_direction: int = 1
        self._on_complete_callbacks: List[Callable] = []
        self._on_frame_change_callbacks: List[Callable] = []
        self._on_state_change_callbacks: List[Callable] = []
        self._logger: AbstractLogger = logger
        self.frames = frames

    def set_state(
        self, 
        state: str, 
        reset_frame: bool = True
    ) -> None:
        if state not in self.frames:
            available_states = list(self.frames.keys())
            raise KeyError(
                f"Invalid state: {state}. Available states: {available_states}"
            )
            
        if state != self.current_state:
            self.current_state = state
            if reset_frame:
                self.frame_index = 0
                self.time_since_last_frame = 0
                
            self._handle_state_change(state)

    def rewind(self) -> None:
        self.frame_index = 0
        self.time_since_last_frame = 0

    def set_play_mode(self, mode: str) -> None:
        if mode not in ("loop", "once", "pingpong"):
            raise ValueError(f"Invalid play mode: {mode}")
        self.play_mode = mode

    def add_complete_callback(self, callback: Callable) -> None:
        if callable(callback):
            self._on_complete_callbacks.append(callback)
        else:
            self._logger.warning("Ignore non callable objects")
    
    def add_frame_change_callback(self, callback: Callable) -> None:
        """Add frame change callback
            
        Args:
            callback: A callback function that receives the current frame index (frame_index: int) -> None
        """
        if callable(callback):
            self._on_frame_change_callbacks.append(callback)
        else:
            self._logger.warning("Ignore non callable objects")
    
    def add_state_change_callback(self, callback: Callable) -> None:
        """Add state change callback
            
        Args:
            callback: A callback function that receives the current state name (state: str) -> None
        """
        if callable(callback):
            self._on_state_change_callbacks.append(callback)
        else:
            self._logger.warning("Ignore non callable objects")

    def handle_animation_end(self) -> None:
        """Handling animation end events (delegates to state_manager)"""
        for callback in self._on_complete_callbacks:
            try:
                callback()
            except Exception as error:
                self._logger.error(
                    f"Callback execution failed: {str(error)}"
                )

    def pause(self) -> None:
        """Pause the animation"""
        self.current_state = None

    def resume(self) -> None:
        """Resume the animation"""
        if not self.current_state and self.frames:
            self.current_state = next(iter(self.frames.keys()))

    def release(self) -> None:
        """Release the resources"""
        self.pause()
        self.current_state = None
        self._on_complete_callbacks.clear()
        self._on_frame_change_callbacks.clear()
        self._on_state_change_callbacks.clear()        

    def _handle_state_change(self, new_state: str) -> None:
        """Handling state change events (delegates to state_manager)"""
        for callback in self._on_state_change_callbacks:
            try:
                callback(new_state)
            except Exception as error:
                self._logger.error(
                    f"State change callback execution failed: {str(error)}"
                )

    def handle_frame_change(self) -> None:
        """Handle frame change event"""
        for callback in self._on_frame_change_callbacks:
            try:
                callback(self.frame_index)
            except Exception as error:
                self._logger.error(
                    f"Frame change callback execution failed: {str(error)}"
                )

@dataclass
class AnimationConfig:
    frames: FramesDict
    frames_times: FramesTimesDict
    frame_scale: Scale = _AnimationMagicNumber.ORIGINAL_IMAGE_FRAME_SCALE
    max_cache_size: int = _AnimationMagicNumber.DEFAULT_MAX_CHACH_SIZE
    play_mode: PlayMode = _AnimationMagicNumber.DEFAULT_PLAY_MODE

@dataclass
class AnimationParamInjection:
    image_provider: Optional[Dict[str, pygame.Surface]] = None
    logger_instance: Optional[AbstractLogger] = None

class FramePlayerEasilyGenerator: 
    """A helper class to create a FramePlayer instance with given parameters"""
    @overload
    @classmethod
    def create(cls,
              frames: Dict[str, List[str]],
              frames_times: float) -> FramePlayer:
        ...
    
    @overload
    @classmethod
    def create(cls,
              frames: Dict[str, List[str]],
              frames_times: FramesTimesDict) -> FramePlayer:
        ...
    
    @overload
    @classmethod
    def create(cls,
              frames: Dict[str, List[pygame.Surface]],
              frames_times: float) -> FramePlayer:
        ...
    
    @overload
    @classmethod
    def create(cls,
              frames: Dict[str, List[pygame.Surface]],
              frames_times: FramesTimesDict) -> FramePlayer:
        ...
    
    @overload
    @classmethod
    def create(cls,
              frames: Dict[str, List[str]],
              frames_times: float,
              scale: Scale) -> FramePlayer:
        ...
    
    @overload
    @classmethod
    def create(cls,
              frames: Dict[str, List[str]],
              frames_times: FramesTimesDict,
              scale: Scale) -> FramePlayer:
        ...
    
    @classmethod
    def create(cls,
              frames: FramesDict,
              frames_times: Union[float, FramesTimesDict],
              scale: Scale = (0, 0),
              play_mode: PlayMode = "loop",
              max_cache_size: int = 200) -> FramePlayer:
        """Create a FramePlayer instance with given parameters
        
        Args:
            frames: animation frames, in the format of:
                {"state1": ["frame1", "frame2", ...], ...} or
                {"state1": [surface1, surface2, ...], ...}
            frame_time: frame interval time (in seconds) for each animation state, in the format of:
                {
                    "state1": duration each frames(in seconds),
                    "state2": duration each frames(in seconds),
                    ...
                }
                Must be completely consistent with the keys of frames
            scale: scaling size, optional, default to (0, 0)
            play_mode: play mode, optional:
                - "loop": Loop playback (default)
                - "once": Play only once
                - "pingpong": Round trip playback
            max_cache_size: cache size
        """
        if isinstance(frames_times, (int, float)):
            frames_times = {
                state: float(frames_times)
                for state in frames.keys()
            }
        else:
            frames_times = frames_times
        
        config = AnimationConfig(
            frames = frames,
            frames_times = frames_times,
            frame_scale = scale,
            play_mode = play_mode,
            max_cache_size = max_cache_size
        )
        
        return FramePlayer(config)

class FramePlayer(AbstractAnimationPlayer):
    """A frame animation player that supports cache optimization and animation event callbacks, 
    inherited from pygame.sprite.Sprite.

    This class provides an efficient frame animation playback system with LRU cache management, 
    multiple playback modes, and event callback functionality.
    Designed to be thread safe and automatically handle resource cleaning, 
    suitable for managing character animations in game development.
    
    ## Features:
        - LRU cache automatic management (preventing memory leaks)
        - Thread safety design
        - Many play modes (loop/once/pingpong)
        - Animation event callback system
        - Smart resource management

    ## Examples:
        ### Basic usage::
        
            anim = FramePlayer(
                frames={"idle": [surface1, surface2], "run": [surface3, surface4]},
                frames_time={"idle": 0.15, "run": 0.1}
            )
            anim.set_state("run")
            anim.update(0.1)
            anim.draw(screen)

        ### Using context manager::
        
            with FramePlayer(...) as anim:
                ...

    ## Note:
        After use, it is recommended to call release() or use the context manager (with statement) to ensure that resources are released correctly

    .. deprecated::
        The `__del__` method has been abandoned. Please use the context manager or manually call `release()` to release resources.
        The timing of calling `__del__`  is unreliable, which may lead to resource leakage.
    """
    
    __slots__ = (
        "_image_source", "frames", "frames_times", "frame_scale", "angle"
        "play_mode", "direction", "_cache_manager", "_state_manager",
        "_play_count", "_on_complete_callbacks", "_on_frame_change_callbacks",
        "_on_state_change_callbacks", "_last_transform", "_last_direction", "_last_angle"
        "image", "rect", "_released", "_pingpong_direction", "_surface_frames", "_logger"
    )
    
    def __init__(
        self, 
        config: AnimationConfig, 
        injection: AnimationParamInjection = AnimationParamInjection()
    ) -> None:
        """Init the FramePlayer with given parameters

        Args:
            config: `AnimatorConfig` object, containing the following parameters:
                frames: Define frame sequences for each animation state, supporting two formats:
                    1. {"state1": ["frame1", "frame2", ...], ...} -
                        The frame name list will be used to search for the corresponding image from image_decider
                    2. {"state1": [surface1, surface2, ...], ...} -
                        Directly use pygame.Surface object

                frames_time: The frame interval time (in seconds) for each animation state, in the format of:
                    {
                        "state1": duration each frames(in seconds),
                        "state2": duration each frames(in seconds),
                        ...
                    }
                    Must be completely consistent with the keys of frames

                frame_scale: Scale size applied to all frames (width, height), give `(0, 0)` means keeping original size (default)

                max_cache_size: The maximum number of cached images, when reached, will eliminate the oldest unused frames

                play_mode: Initial playback mode, optional:
                    - "loop": Loop playback (default)
                    - "once": Play only once
                    - "pingpong": Round trip playback
            injection: `AnimatorParamInjection` object, containing the following parameters:
                image_provider: Provide a mapping dictionary from frame name to image surface. If None, the global resource_manager.
                get_image method is used by default to obtain the image

                logger_instance: Provide a logger instance for logging, if None, the global logger is used.

                state_manager: Provide a state manager instance for logging, if None, the AnimatorStateManager() is used.

                cache_manager: Provide a cache manager instance for LRU cache, if None, the AnimatorCacheManager() is used.

        Raises:
            ValueError: When the keys of frames and frames_time do not match
            TypeError: When the input parameter type does not meet the requirements

        ## Note:
            Suggest using frame images of the same size for optimal performance
        """
        super().__init__()
        self._image_source = injection.image_provider or {} # Advance declaration to prevent AttributeError during detection
        self._validate_init_params(config, injection)

        # Basic Parameters
        self.frames_times = config.frames_times
        self.frame_scale: Scale = config.frame_scale
        self.play_mode: PlayMode = config.play_mode
        self.direction: Direction = (False, False)
        self.angle: float = 0.0
        self._logger = injection.logger_instance or DefaultLogger()

        self._process_init_frame(config)

        # systems init
        self._cache_manager = \
            _FrameCacheManager(
                _CacheManagerDeps(
                    config.max_cache_size,
                    lambda: self.frame_scale,
                    lambda: self.direction,
                    self._process_image,
                    self._create_error_surface,
                    lambda: self._surface_frames,
                    self._logger
                )
            )
        self._state_manager = \
            _FrameStateManager(
                self.frames,
                self._logger
            )
        self._state_manager.set_state(next(iter(self.frames.keys())))

        # track status
        self._last_scale: Scale = (0, 0)
        self._last_direction: Direction = (False, False)
        self._last_angle: float = 0.0
        self.image: Optional[pygame.Surface] = None
        self.rect: Optional[pygame.Rect] = None
        self._released = False

        # Initialize image
        if self._surface_frames:
            self.image = self._process_surface_frame(
                self.frames[self._state_manager.current_state][0]
                )
        else:
            self.image = self._cache_manager.get_cached_image(
                str(self.frames[self._state_manager.current_state][0])
            )
        self.rect = self.image.get_rect()

    def _process_init_frame(self, config: AnimationConfig) -> None:
        self._surface_frames = False

        _first_frame = next(iter(config.frames.values()))
        if _first_frame != [] and isinstance(_first_frame[0], pygame.Surface):
            self._surface_frames = True
            self.frames = {
                k: [frame.copy() for frame in v] 
                for k, v in config.frames.items()
            }
        else:
            self.frames = config.frames

    def _transform_frame(self, img: pygame.Surface) -> pygame.Surface:
        """Transform the frame with self.frame_scale and self.direction
        Args:
            img: Original frame image

        Returns:
            Transformed frame image
        """
        if self.frame_scale != (0, 0) and self.frame_scale != img.get_size():
            img = pygame.transform.scale(img, self.frame_scale)
        if any(self.direction):
            img = pygame.transform.flip(img, *self.direction)
        if self.angle % 360 != 0.0:
            img = pygame.transform.rotate(img, self.angle)
        return img

    def _process_surface_frame(self, surface: pygame.Surface) -> pygame.Surface:
        """Process self.frame_scale with self.direction to the Surface

        Args:
            surface: Original pygame.Surface

        Returns:
            Processed surface with scaling and flip
        """

        return self._transform_frame(surface.copy())
    
    def _process_image(self, frame_name: str) -> pygame.Surface:
        """Actual image processing logic
        Args:
            frame_name: Original image resource name

        Returns:
            Processed surface with scaling and flip

        Raises:
            KeyError: Image resource not found
        """
        if frame_name not in self._image_source:
            raise KeyError(f"Invalid image resource: {frame_name}")
        
        return self._transform_frame(self._image_source[frame_name])

    def _get_frame(self, state: str, frame_index: int) -> pygame.Surface:
        """Get given state's and frame index's frame
        
        Args:
            state: animation state name
            frame_index: frame index
            
        Returns:
            frame image surface

        Raises:
            KeyError: State not found
            IndexError: Index out of range
        """
        if state not in self.frames:
            raise KeyError(f"Invalid state: {state}")
        
        if frame_index < 0 or frame_index >= len(self.frames[state]):
            raise IndexError(f"Index out of range: {frame_index}")
        
        if self._surface_frames:
            surface: pygame.Surface = self.frames[state][frame_index]
            return self._process_surface_frame(surface)
        else:
            frame_name: str = self.frames[state][frame_index]
            return self._cache_manager.get_cached_image(frame_name)

    
    def _validate_init_params(
        self,
        config: AnimationConfig,
        injection: AnimationParamInjection
    ) -> None:
        """Verify the validity of initialization parameters
        Args:
            frames: Animation frames dict {state name: [frames name list]}
            frames_time: duration each frame(in seconds) {state name: duration}

        Raises:
            ValueError: State definition is incomplete or missing
            TypeError: Args type error
        """
        self._vaildate_init_config(config)
        self._vaildate_init_injection(injection)

    @staticmethod
    def _vaildate_init_injection(injection: AnimationParamInjection) -> None:
        if not isinstance(injection, AnimationParamInjection):
            raise TypeError("injection must be AnimatorParamInjection")
        image_provider = injection.image_provider
        logger_instance = injection.logger_instance
        if image_provider is not None and not isinstance(image_provider, dict):
            raise TypeError("image_provider must be a dict")
        elif image_provider is not None:
            for name, img in image_provider.items():
                if not isinstance(img, pygame.Surface):
                    raise TypeError(
                        f"image_provider[{name}] must be a pygame.Surface"
                    )
        if (logger_instance is not None and
            not isinstance(logger_instance, AbstractLogger)):
            raise TypeError("logger_instance must be a AbstractLogger")

        
    def _vaildate_init_config(self, config: AnimationConfig) -> None:
        if not isinstance(config, AnimationConfig):
            raise TypeError("config must be AnimatorConfig")
        
        frames = config.frames
        frames_times = config.frames_times
        try:
            if len(frames) == 0:
                raise ValueError("frames must not be empty")
            
            if frames.keys() != frames_times.keys():
                missing = (set(frames.keys())
                           .symmetric_difference(frames_times.keys())) 
                # A.symmetric_difference(B) = (A △ B) = (A ∪ B) - (A ∩ B)
                raise ValueError(
                    f"States definition incomplete, missing: {missing}"
                )

            for state, frame_list in frames.items():
                if not frame_list:
                    raise ValueError(f'frames["{state}"] must not be empty')
                
                if not isinstance(frame_list, list):
                    raise TypeError(f'frames["{state}"] must be a list')
                
                self._validate_and_load_frames(state, frame_list)
            
            for state, frame_time in frames_times.items():
                if not isinstance(frame_time, (float, int)):
                    raise TypeError(f'frames_time["{state}"] must be a float')
        except AttributeError:
            raise TypeError("frames and frames_time must be dicts")  
         
        frame_scale = config.frame_scale
        max_cache_size = config.max_cache_size
        play_mode = config.play_mode
        if not (isinstance(frame_scale, tuple) or 
                all(isinstance(i, (int, float)) for i in frame_scale)):
            raise TypeError("frame_scale must be a tuple of two numbers")
        if (not isinstance(max_cache_size, int) or
            max_cache_size < _AnimationMagicNumber.DEFAULT_MAX_CHACH_SIZE):
            raise ValueError(
                f"max_cache_size must be an integer greater than or equal to {
                    _AnimationMagicNumber.DEFAULT_MAX_CHACH_SIZE
                }"
            )
        if not play_mode in get_args(PlayMode):
            raise ValueError(
                f"Invalid play mode: {play_mode},"
                "play mode must be one of {get_args(PlayMode)}"
            )

    def _validate_and_load_frames(self, state: str, frame_list: list) -> None:
        """validate and load frame images from file path or pygame.Surface
        Args:
            state: animation state name
            frame_list: frame image list (str or pygame.Surface)
        Raises:
            TypeError: Invalid frame type"""
        for i, frame in enumerate(frame_list):
            if not isinstance(frame, (str, pygame.Surface)):
                raise TypeError(
                    f'frames["{state}"][{i}] must be str, filepath or pygame.Surface, '
                    f'got {type(frame).__name__}'
                )
            
            if isinstance(frame, str) and frame not in self._image_source:
                try:
                    loaded_surface = pygame.image.load(frame)
                    self._image_source[frame] = loaded_surface
                except (pygame.error, FileNotFoundError) as e:
                    raise ValueError(
                        f'frames["{state}"][{i}]: '
                        'Cannot load image resource "{frame}" - {e}'
                    )

    @staticmethod
    def _create_error_surface() -> pygame.Surface:
        """Generate error prompt image"""
        surf = pygame.Surface(_AnimationMagicNumber.ERROR_SURFACE_SIZES)
        surf.fill(_AnimationMagicNumber.ERROR_RECT_COLOR)
        return surf
    
    @property
    def is_playing(self) -> bool:
        """Return True if the animation is playing"""
        return self._state_manager.current_state is not None

    # region ################## cache API #################

    def clear_cache(self) -> None:
        """Clear all cached images"""
        self._cache_manager.clear()

    def set_cache_size(self, size: int) -> None:
        """Dynamically adjust cache size
        
        Args:
            size: new cache size (minimum 10)

        Raises:
            ValueError: Size is less than 10
        """
        self._cache_manager.set_max_cache_size(size)
    # endregion

    # region #################### Animation Control System ####################
    def get_state(self) -> str | None:
        return self._state_manager.current_state
    
    def set_state(self, 
                  state: str, 
                  reset_frame: bool = True) -> None:
        """Set now playing state (delegates to state_manager)"""
        self._state_manager.set_state(state, reset_frame)
    
    def rewind(self) -> None:
        """Reset to the starting frame (delegates to state_manager)"""
        self._state_manager.rewind()

    def set_play_mode(self, mode: str) -> None:
        """Set play mode
        
        Args:
            mode: will set play mode ("loop"/"once"/"pingpong")
            
        Raises:
            ValueError: Invalid play mode
        """
        self._state_manager.set_play_mode(mode)

    def add_complete_callback(self, callback: Callable) -> None:
        """Add animation complete callback
        
        Args:
            callback: No parameter callback function
        """
        self._state_manager.add_complete_callback(callback)

    def _handle_animation_end(self) -> None:
        """Handling animation end events (delegates to state_manager)"""
        self._state_manager.handle_animation_end()

    def pause(self) -> None:
        """Pause animation"""
        self._state_manager.pause()

    def resume(self) -> None:
        """Resume playback (Resume from the current frame)"""
        self._state_manager.resume()
    # endregion

    # region #################### core update logic ####################
    def update_frame(
            self, 
            dt: float = 1/60, 
            direction: Direction = (False, False), 
            scale: Scale = (0, 0),
            angle: float = 0.0
        ) -> None:
        """Update animation frame
                Args:
            dt: Time elapsed since the previous frame (in seconds), default is 1/60
            direction: Image flipping direction (flip_x, flip_y)
            transform: Image scaling size (width, height)
            angle: Image rotation angle (in degrees)
        """
        if self._state_manager.current_state is None:    
            return
        if self.direction != direction:
            self.direction = direction
        if self.frame_scale != scale:
            self.frame_scale = scale
        if self.angle != (normalized_angle := angle % 360):
            self.angle = normalized_angle

        self._state_manager.time_since_last_frame += dt
        frame_duration = self.frames_times[self._state_manager.current_state]
        
        with self._cache_manager.lock:
            if self._state_manager.time_since_last_frame >= frame_duration:
                self._state_manager.time_since_last_frame = 0
                self._advance_frame()
        
        # Not using locks in the code below is to prevent lock blocking
        if scale != self._last_scale or direction != self._last_direction:
            self._last_scale = scale
            self._last_direction = direction
            self._update_image()

    def _advance_frame(self) -> None:
        """Advance to the next frame (based on playback mode)"""
        if self._state_manager.current_state is None:
            return
        
        frame_count = len(self.frames[self._state_manager.current_state])
        prev_frame_index = self._state_manager.frame_index
        
        if self.play_mode == "pingpong":
            next_index = self._state_manager.frame_index + self._pingpong_direction
            if next_index < 0 or next_index >= frame_count:
                self._pingpong_direction *= -1
                next_index = max(0, min(next_index + self._pingpong_direction * 2, frame_count - 1))
                self._state_manager.handle_animation_end()            
            self._state_manager.frame_index = next_index
        elif self.play_mode == "loop":
            self._state_manager.frame_index = (self._state_manager.frame_index + 1) % frame_count
        elif self.play_mode == "once":
            self._state_manager.frame_index += 1
            if self._state_manager.frame_index >= frame_count:
                self._state_manager.frame_index = frame_count - 1
                self._state_manager.handle_animation_end()
                self.pause()
        if self._state_manager.frame_index != prev_frame_index:
            self._update_image()

    def _update_image(self) -> None:
        """Update the currently displayed image"""
        with self._cache_manager.lock:
            if self._state_manager.current_state is None or not self.rect:
                return

            try:
                current_frames_list: List[Union[str, pygame.Surface]] = \
                    self.frames[self._state_manager.current_state]
                current_frame: Union[str, pygame.Surface] = \
                    current_frames_list[self._state_manager.frame_index]
                
                if self._surface_frames:
                    self.image = self._process_surface_frame(current_frame)
                else:
                    self.image = self._cache_manager.get_cached_image(current_frame)

                old_center = self.rect.center if self.rect else None
                self.rect = self.image.get_rect()
                if old_center:
                    self.rect.center = old_center

                self._state_manager.handle_frame_change()
            except Exception as error:
                self._logger.error(f"Update image failed: {str(error)}")
                self.image = self._create_error_surface()
                self.rect = self.image.get_rect()

    def add_frame_change_callback(self, callback: Callable) -> None:
        """Add frame change callback
            
        Args:
            callback: A callback function that receives the current frame index (frame_index: int) -> None
        """
        self._state_manager.add_complete_callback(callback)

    def add_state_change_callback(self, callback: Callable) -> None:
        """Add state change callback
            
        Args:
            callback: A callback function that receives the current state name (state: str) -> None
        """
        self._state_manager.add_state_change_callback(callback)

    # endregion

    # region #################### resources management ####################
    def release(self) -> bool:
        """Release all resources and return whether the release operation was executed

        Returns:
            True: Actually executed resource release
            False: Resource released (skipped)
        
        Raises:
            Exception: Resource release failed
        """
        if self._released:
            self._logger.info("Resource released (skipped safely)")
            return False

        with self._cache_manager.lock:
            try:
                self._state_manager.release()
                self._cache_manager.release(self.image)
                self.image = None
                self.rect = None
                return True
            except Exception as error:
                self._logger.error(
                    f"Resource release failed: {str(error)}",
                    exc_info=True
                )
                raise
            finally:
                self._released = True
                self._state_manager = None
                self._cache_manager = None
                super().kill()
                self._logger.info("Resource release status updated")
    
    def kill(self) -> None:
        self.release()
                
    def __del__(self) -> None:
        """
        DEPRECATED: 
        Please use the release() method instead. This is a safety net for 
        when users forget to explicitly release resources.
        
        Note: Relying on __del__ is not recommended as it's not guaranteed
        to be called promptly or at all. Always use release() or context manager.
        """
        if not self._released:
            self.release()

    def __enter__(self) -> FramePlayer:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
    # endregion

    # region #################### draw frame surfaces ####################  
    def draw(self, surface: pygame.Surface) -> None:
        """Draw sprite to the Surface
        
        Args:
            surface (pygame.Surface): The surface to be drawn
        
        Raises:
            ValueError: The image or rect has not been set yet
        """
        if self.image is None:
            raise ValueError("Image not set")
        if not hasattr(self, 'rect') or self.rect is None:
            raise ValueError("Rect not set")
        surface.blit(self.image, self.rect)
    # endregion

    # region #################### debugger ####################
    @property
    def cache_info(self) -> Dict[str, Union[int, List[str]]]:
        """Get cache state info
        
        Returns:
            Dict containing cache size and sample keys
        """
        return self._cache_manager.info

    def draw_debug_info(self, surface: pygame.Surface, pos: Tuple[int, int]) -> None:
        """Draw debug info to the given surface"""
        info = self.cache_info
        font = pygame.font.SysFont(None, _AnimationMagicNumber.DEBUG_FONT_SIZE)
        
        texts = [
            f"State: {self.get_state or 'None'}",
            f"Frame: {self.frame_index}",
            f"Cache: {info['cache_size']}/{info['max_size']}",
            f"PlayMode: {self.play_mode}"
        ]
        
        for i, text in enumerate(texts):
            text_surface = font.render(text, True, (255, 255, 255))
            surface.blit(text_surface, (pos[0], pos[1] + i * font.get_height()))

    @property
    def frame_index(self) -> int:
        return self._state_manager.frame_index
    
    def private_dirs(self) -> List[str]:
        """Get public attributes"""
        all_attrs = super().__dir__()
        public_attrs = [
            attr for attr in all_attrs 
            if not attr.startswith('_') or 
            (attr.startswith('__') and attr.endswith('__'))
        ]
        return sorted(public_attrs)
    
    def get_self_attrs(self) -> List[str]:
        """Get all new create attributes of the object"""
        all_attrs = self.__dir__()
        new_attrs = set(all_attrs) - set(dir(super()))
        return [attr for attr in sorted(new_attrs) if not attr.startswith('_')]
    # endregion
