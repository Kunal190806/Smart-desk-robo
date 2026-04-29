import pygame
import math
import time
import random

import threading

# ---------- UI STATE ----------
pygame.init()
screen = pygame.display.set_mode((400, 400))
clock = pygame.time.Clock()

BG = (18, 18, 18)
WHITE = (255, 255, 255)

# Current visual expression – updated by robo_brain via callback
current_expression = "idle"
eye_height = 70
is_speaking = False
talk_phase = 0

def set_state(state: str):
    """Callback invoked by robo_brain to update UI state."""
    global current_expression, is_speaking
    current_expression = state
    if state == "speaking":
        is_speaking = True
    else:
        is_speaking = False

# ---------- IMPORT ROBOT BRAIN ----------
import robo_brain

# Register UI callback so the brain can drive the face
robo_brain.set_state_callback(set_state)

# Start background voice loop (daemon thread)
robo_brain.start()

# ---------- DRAW FACE ----------
def draw_face(offset):
    global eye_height, talk_phase

    # Adjust eye height based on expression
    if current_expression == "listening":
        target = 40
    elif current_expression == "thinking":
        target = 50
    elif current_expression == "error":
        target = 60
    else:
        target = 70

    eye_height += (target - eye_height) * 0.2

    # Eyes
    pygame.draw.rect(screen, WHITE, (130, 150 + offset, 35, eye_height), border_radius=18)
    pygame.draw.rect(screen, WHITE, (240, 150 + offset, 35, eye_height), border_radius=18)

    # Mouth / speaking animation
    if is_speaking:
        talk_phase += 0.3
        mouth = abs(math.sin(talk_phase)) * 20
        pygame.draw.ellipse(screen, WHITE, (180, 250 + offset, 40, mouth + 5))
    elif current_expression == "alert":
        pygame.draw.circle(screen, WHITE, (200, 260 + offset), 10)
    elif current_expression == "error":
        pygame.draw.arc(screen, WHITE, (165, 260 + offset, 70, 40), math.pi, 2 * math.pi, 4)
    else:
        pygame.draw.arc(screen, WHITE, (165, 240 + offset, 70, 40), 0, math.pi, 4)

# ---------- MAIN LOOP ----------
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    screen.fill(BG)
    offset = math.sin(time.time() * 1.5) * 3
    draw_face(offset)
    pygame.display.update()
    clock.tick(60)