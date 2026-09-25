"""Runtime, display, layout, color, and font configuration."""

import pygame

pygame.init()
pygame.font.init()

ADMIN_CONTROL = False

info = pygame.display.Info()
WIDTH, HEIGHT = info.current_w, info.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Shinobi Generátor - Vytvoř si postavu")
clock = pygame.time.Clock()
FPS = 60

TOP_BAR_H = 100
BOTTOM_MARGIN = 30
CONTENT_TOP = TOP_BAR_H + 15


def avail_height():
    return max(200, HEIGHT - TOP_BAR_H - BOTTOM_MARGIN)


def centered_top(block_height, top=CONTENT_TOP, bottom_margin=BOTTOM_MARGIN):
    space = HEIGHT - top - bottom_margin
    return top + max(0, (space - block_height) // 2)


def generic_layout(panel_height=250, button_h=55, gap=28, extra_top=0, back_h=50):
    top = max(CONTENT_TOP, extra_top)
    avail = HEIGHT - top - BOTTOM_MARGIN
    fixed = gap + button_h + gap + back_h
    if avail - fixed < 90:
        gap = max(12, gap - 12)
        fixed = gap + button_h + gap + back_h
    max_panel = max(60, avail - fixed)
    panel_height = min(panel_height, max(30, max_panel))
    panel_height = max(30, panel_height)
    block_h = panel_height + fixed
    panel_y = top + max(0, (avail - block_h) // 2)
    button_y = panel_y + panel_height + gap
    back_y = button_y + button_h + gap
    return panel_y, button_y, back_y, panel_height


def warning_layout(button_h=60):
    warn_y = centered_top(240 + button_h)
    button_y = warn_y + 240
    back_y = button_y + button_h + 28
    return warn_y, button_y, back_y


def summary_layout():
    row1_h, row2_h, gap = 46, 45, 14
    bottom_h = row1_h + gap + row2_h
    panel_y = CONTENT_TOP
    panel_h = max(320, HEIGHT - BOTTOM_MARGIN - bottom_h - 20 - panel_y)
    row1_y = panel_y + panel_h + 20
    row2_y = row1_y + row1_h + gap
    return panel_y, panel_h, row1_y, row2_y


BG_DARK = (12, 12, 20)
BG_PANEL = (32, 32, 48)
BG_PANEL2 = (45, 45, 65)
BG_PANEL3 = (20, 20, 32)
ACCENT = (255, 140, 0)
ACCENT_HL = (255, 170, 60)
ACCENT_DARK = (200, 110, 0)
BLUE = (100, 180, 255)
BLUE_DARK = (70, 140, 200)
GOLD = (255, 220, 80)
GOLD_DARK = (200, 170, 40)
GREEN = (120, 230, 160)
RED = (255, 100, 100)
PURPLE = (190, 130, 255)
PURPLE_DARK = (140, 80, 200)
WHITE = (245, 245, 250)
GRAY = (160, 160, 180)
DARKGRAY = (90, 90, 110)
SHADOW = (0, 0, 0, 80)

font_title = pygame.font.SysFont("arial", 48, bold=True)
font_h1 = pygame.font.SysFont("arial", 32, bold=True)
font_h2 = pygame.font.SysFont("arial", 24, bold=True)
font_med = pygame.font.SysFont("arial", 19)
font_small = pygame.font.SysFont("arial", 16)
font_tiny = pygame.font.SysFont("arial", 14)
