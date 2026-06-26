"""
FLUX/SD character sprite generator — DEPRECATED.
Vyom Ai Cloud no longer uses character sprites.
All rendering uses stock footage, screen captures, Manim diagrams, and code snippets.
"""
import os
import warnings

warnings.warn("flux_gen is deprecated in Vyom Ai Cloud tech/AI pipeline. Character sprites are no longer used.", DeprecationWarning, stacklevel=2)

USE_FLUX_GEN = False


def generate_character_base(char_name: str, force: bool = False):
    return None


def generate_all_bases(force: bool = False) -> dict:
    return {}


if __name__ == "__main__":
    print("flux_gen is deprecated in Vyom Ai Cloud tech/AI pipeline.")
    print("Character sprites are no longer used. Remove this module from imports.")
