import pygame
import random
import time
import math

pygame.init()

# Screen
WIDTH, HEIGHT = 400, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dasai Mochi Clone")

clock = pygame.time.Clock()

# Colors
BG = (18, 18, 18)
WHITE = (255, 255, 255)

# Animation states
eye_height = 70
target_eye_height = 70

mouth_curve = 1
target_mouth_curve = 1

# Timing
last_expression_change = time.time()
expression_delay = random.uniform(3, 6)

blink_state = "open"
blink_timer = time.time()
blink_interval = random.uniform(2.5, 5)

# Easing function (smooth like real UI)
def ease_in_out(t):
    return t * t * (3 - 2 * t)

# Lerp with easing
def smooth(current, target, speed):
    t = speed
    t = ease_in_out(t)
    return current + (target - current) * t

def draw_face(offset_y):
    # Eye positions (more centered like Dasai)
    left_eye_x = 130
    right_eye_x = 240
    eye_y = 150 + offset_y

    # Eyes (rounded vertical)
    pygame.draw.rect(screen, WHITE, (left_eye_x, eye_y, 35, eye_height), border_radius=18)
    pygame.draw.rect(screen, WHITE, (right_eye_x, eye_y, 35, eye_height), border_radius=18)

    # Mouth (soft + centered)
    mouth_rect = pygame.Rect(165, 240 + offset_y, 70, 40)

    if mouth_curve > 0:
        pygame.draw.arc(screen, WHITE, mouth_rect, 0, math.pi, 4)
    else:
        pygame.draw.arc(screen, WHITE, mouth_rect, math.pi, 2 * math.pi, 4)

running = True

while running:
    screen.fill(BG)
    now = time.time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 🌊 Subtle floating (VERY minimal like Dasai)
    float_offset = math.sin(now * 1.5) * 3

    # 😄 Expression change (slow, natural)
    if now - last_expression_change > expression_delay:
        target_mouth_curve = random.choice([1, 1, 1, -1])  # mostly happy
        last_expression_change = now
        expression_delay = random.uniform(3, 6)

    # 👀 Blink system (multi-stage like real)
    if blink_state == "open" and now - blink_timer > blink_interval:
        blink_state = "closing"
        blink_timer = now

    elif blink_state == "closing":
        target_eye_height = 5
        if eye_height < 10:
            blink_state = "closed"
            blink_timer = now

    elif blink_state == "closed":
        if now - blink_timer > 0.08:  # tiny pause
            blink_state = "opening"

    elif blink_state == "opening":
        target_eye_height = 70
        if eye_height > 65:
            blink_state = "open"
            blink_timer = now
            blink_interval = random.uniform(2.5, 5)

    # Smooth transitions
    eye_height = smooth(eye_height, target_eye_height, 0.15)
    mouth_curve = smooth(mouth_curve, target_mouth_curve, 0.08)

    draw_face(float_offset)

    pygame.display.update()
    clock.tick(60)

pygame.quit()