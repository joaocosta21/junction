# MENU-1 questions

## 1. For Valio: is there any data on which products can do the same job in a dish?

**Context:** Valio's scenarios ask for substitutions "through recipe logic rather than a simple SKU swap". The product file lists 249 substitutes by product id, and nothing about what an ingredient does in a dish.
**We did:** wrote our own illustrative recipe table (`src/tta/menus/recipes.yaml`, 9 dishes): each ingredient has a role and an ordered list of other product types that do the same job, each with a reason. The menu planner tries them in order when the recipe's own product type cannot arrive in time, and rule F-09 sends every such stand-in to the purchasing manager.
**We got:** in the capture `2026-11-14-demo`, plain quark (`maitorahka`, 10 products) cannot be had by Monday 16 Nov with confirmed stock: 6 are past their order cut-off and 4 have no confirmed quantity. The planner offers 12 kg of a natural yoghurt instead (`464615`, Valio A+ greek natural yoghurt 1 kg), with the reason "A thick natural yoghurt gives the same tangy base; the dessert is runnier and has less protein".
**Example to show:** `POST /v1/menus/plan` with beef stew and berry quark dessert, 120 servings each, needed 2026-11-16, confirmed only; the plan's quark line, and the offer's line 4 with `stands_in_for: quark`.
**Ask:** "Do you hold, or plan to publish, any data on which products can replace which in a kitchen (for example a functional group, or the substitutes your own sales staff suggest), or is a buyer-side recipe table like ours the expected approach?"
**If no answer, we build:** nothing more: the recipe table stays ours, labelled illustrative, and every stand-in goes to a human (F-09).
