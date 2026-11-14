"""Recipe logic: a menu becomes one offer, with substitutions by an ingredient's role in the dish (task MENU-1)."""

from tta.menus.planner import plan_menu
from tta.menus.recipes import RECIPES_PATH, Recipe, RecipeLoadError, load_recipes, shipped_recipes

__all__ = ["RECIPES_PATH", "Recipe", "RecipeLoadError", "load_recipes", "plan_menu", "shipped_recipes"]
