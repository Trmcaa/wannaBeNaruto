"""Shared rendering helpers used by the game UI."""

import pygame

from ..config.settings import *


def fit_font(text, max_width, fonts):
    for font in fonts:
        if font.size(text)[0] <= max_width:
            return font, text
    smallest = fonts[-1]
    truncated = text
    while truncated and smallest.size(truncated + "…")[0] > max_width:
        truncated = truncated[:-1]
    return smallest, (truncated + "…" if truncated != text else text)


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_gradient_rect(surf, rect, top_color, bottom_color, border_radius=0):
    rect = pygame.Rect(rect)
    if rect.width <= 0 or rect.height <= 0:
        return
    grad = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    steps = max(1, rect.height)
    for y in range(steps):
        t = y / max(1, steps - 1)
        col = _lerp_color(top_color, bottom_color, t)
        pygame.draw.line(grad, col, (0, y), (rect.width, y))
    if border_radius > 0:
        mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=border_radius)
        grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(grad, rect.topleft)


def draw_glow_rect(surf, rect, color, border_radius=20, layers=5, max_alpha=55, spread=3):
    rect = pygame.Rect(rect)
    pad = spread * layers + 2
    glow = pygame.Surface((rect.width + pad * 2, rect.height + pad * 2), pygame.SRCALPHA)
    cx, cy = glow.get_width() // 2, glow.get_height() // 2
    for i in range(layers, 0, -1):
        alpha = max(1, int(max_alpha * (i / layers) ** 2))
        w = rect.width + spread * 2 * i
        h = rect.height + spread * 2 * i
        glow_rect = pygame.Rect(0, 0, w, h)
        glow_rect.center = (cx, cy)
        pygame.draw.rect(glow, (*color[:3], alpha), glow_rect,
                         border_radius=border_radius + spread * i)
    surf.blit(glow, (rect.centerx - cx, rect.centery - cy))


def draw_soft_shadow(surf, rect, border_radius=18, offset=6, layers=3, max_alpha=110):
    rect = pygame.Rect(rect)
    shadow = pygame.Surface((rect.width + layers * 4, rect.height + layers * 4), pygame.SRCALPHA)
    cx, cy = shadow.get_width() // 2, shadow.get_height() // 2
    for i in range(layers, 0, -1):
        alpha = max(1, int(max_alpha * (i / layers)))
        width = rect.width + i * 3
        height = rect.height + i * 3
        shadow_rect = pygame.Rect(0, 0, width, height)
        shadow_rect.center = (cx, cy + offset)
        pygame.draw.rect(shadow, (0, 0, 0, alpha // layers), shadow_rect,
                         border_radius=border_radius + i)
    surf.blit(shadow, (rect.centerx - cx, rect.centery - cy))


def draw_panel(surf, rect, base_color, border_color, border_radius=20, border_width=3,
               glow=True, shine=True):
    rect = pygame.Rect(rect)
    draw_soft_shadow(surf, rect, border_radius=border_radius)
    if glow:
        draw_glow_rect(surf, rect, border_color, border_radius=border_radius,
                       layers=4, max_alpha=40)
    top_shade = tuple(min(255, color + 14) for color in base_color)
    bottom_shade = tuple(max(0, color - 10) for color in base_color)
    draw_gradient_rect(surf, rect, top_shade, bottom_shade, border_radius=border_radius)
    if shine:
        shine_rect = pygame.Rect(rect.x + 4, rect.y + 3, rect.width - 8,
                                 max(2, rect.height // 6))
        shine_surf = pygame.Surface((shine_rect.width, shine_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(shine_surf, (255, 255, 255, 22), shine_surf.get_rect(),
                         border_radius=max(1, border_radius - 4))
        surf.blit(shine_surf, shine_rect.topleft)
    pygame.draw.rect(surf, border_color, rect, border_width, border_radius=border_radius)


def draw_corner_ornaments(surf, rect, color, size=22, thickness=3):
    rect = pygame.Rect(rect)
    corners = [
        (rect.left, rect.top, 1, 1),
        (rect.right, rect.top, -1, 1),
        (rect.left, rect.bottom, 1, -1),
        (rect.right, rect.bottom, -1, -1),
    ]
    for x, y, dx, dy in corners:
        pygame.draw.line(surf, color, (x, y), (x + size * dx, y), thickness)
        pygame.draw.line(surf, color, (x, y), (x, y + size * dy), thickness)
        pygame.draw.circle(surf, color, (x, y), thickness)


def build_background_surface():
    surf = pygame.Surface((WIDTH, HEIGHT))
    top = BG_DARK
    bottom = (BG_DARK[0] + 10, BG_DARK[1] + 8, BG_DARK[2] + 22)
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        pygame.draw.line(surf, _lerp_color(top, bottom, t), (0, y), (WIDTH, y))
    vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    corner_r = int(max(WIDTH, HEIGHT) * 0.75)
    for corner in [(0, 0), (WIDTH, 0), (0, HEIGHT), (WIDTH, HEIGHT)]:
        pygame.draw.circle(vignette, (0, 0, 0, 10), corner, corner_r)
    surf.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return surf
