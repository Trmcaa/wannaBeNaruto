"""Application entry point and Pygame main loop."""

import sys

import pygame

from ..core.game import FPS, SOUND, clock, Game


def main():
    game = Game()
    SOUND.start_ambient()
    running = True
    while running:
        game.build_buttons()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            result = game.handle_event(event)
            if result == "quit":
                running = False

        game.update_anim()
        game.update_auto_roll()
        game.update_particles(1.0 / FPS)
        game.update_bursts(1.0 / FPS)
        game.draw()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
