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

running = True
while running:
    dt = clock.tick(60) / 1000.0  # Calculate frame delta time
    
    # Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if animation.get_state() == "idle":
                    animation.set_state("walk")
                elif animation.get_state() == "walk":
                    animation.set_state("idle")
    
    # Update animation
    animation.update_frame(dt)
    
    # Draw
    screen.fill((0, 0, 0))
    animation.rect.center = (400, 300)  # Set position
    animation.draw(screen)
    
    pygame.display.flip()

# Cleanup resources
animation.kill()
pygame.quit()