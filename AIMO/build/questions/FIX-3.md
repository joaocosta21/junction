# FIX-3 — questions (1 for the team)

Product counts are from the whole catalog (17,546 products). Stock and prices are from the demo capture of 14 Nov 02:52, a sample of live calls.

## Q1 — For the team: is a milk for coffee what a buyer who asks for "milk" expects?

**Context:** the product type `milk` now leaves out the 13 products of category 10400 that are not milk: 11 sour milks, a coffee drink and a soy yoghurt. 78 of the 91 stay. Four of the 78 are milks sold for coffee: `462626` and `464237` "Valio coffee milk" (kahvimaito), `473142` "Valio coffee milk drink vanilla" and `463380` "Arla Cafè milk 1 L UHT lactose free".
**We did:** kept all four in `milk`: their names say milk ("coffee milk", "kahvimaito", "Cafè milk"). Only `469266` "Valio Latte original coffee drink" (maitokahvijuoma), whose name says coffee drink, is left out.
**We got:** tonight's best option for "1,000 litres of lactose-free milk" takes 565 of its 1,000 litres from `463380` (698 units confirmed, €2.65). Without it the confirmed lactose-free milks cover 435 litres (`469363` 384 + `462775` 51) and option 1 becomes a partial fill.
**Example to show:** `463380` "Arla Cafè milk 1 L UHT lactose free" in option 1 of scenario 1; `473142` "Valio coffee milk drink vanilla 1 l lactose free UHT", vanilla flavoured, as a candidate for the same request.
**Ask:** "A request for milk can be answered with a milk for coffee, and with the vanilla one. Is that expected, or did we get something wrong?"
**If no answer, we build:** all four stay in `milk`. Leaving one out is one term in `exclude_terms` of `milk` in `src/tta/catalog/product_types.yaml` ("vanilla" matches only `473142` among the 78).
