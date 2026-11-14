# Second booth visit — new questions after Valio's answers (Saturday 14 Nov)

**How to use:** read the **Ask** line out loud. Show the example only if they ask "where?". Write the answer under the question.
Every figure below was measured today on the recording of Saturday 02:52, with the app run offline.
Questions 1 to 4 change what we build tonight. Ask them first. Question 5 can wait until last.

**1. How and when do you judge?**
- **Context:** our public link reads your mock on real time. You told us the data is static and that we may choose the date.
- **Example:** every product with confirmed stock in our recording must be ordered by Sunday 15 Nov 17:00. After that, on real time, nothing can be promised for Monday. So we plan to run the public link on the recorded answers with the clock fixed at Saturday 14 Nov 02:52, and to say so on every page.
- **Ask:** "Do you judge at our table, from the video, or by opening our link, and when? Is a link that runs on recorded mock answers with a fixed, labelled clock fine?"
- **Answer:** you are overcomplicating... just provide the product to show and be the best in order to show them the best date and exmaple of our app.

**2. Who confirms an order, and may ordering alone stay as a setting?**
- **Context:** you told us to switch off automatic ordering: the agent suggests, the user confirms.
- **Example:** the allergy ward asks for 200 litres of a milk substitute. Everything is confirmed, €402.00, within the ward's €500 limit. Until now the agent ordered it alone. Now it prepares the order and waits for a person.
- **Ask:** "Who should confirm: the person who asked, or the person responsible for purchasing? And may we keep 'order alone within these limits' as a setting the buyer can switch on, off by default, and show it once?"
- **Why we ask:** the judging criterion scores "what the agent can decide alone".
- **Answer:** tbh after and if you are 100% sure yes

**3. Which suggestions from past orders do you value?**
- **Context:** we generate an order history for each customer type, and the agent uses it.
- **Example:** our hotel kitchen has a weekly order of one lactose-free milk (product 469363). Asked today for "100 litres of milk", the agent picks another milk (463047), because it does not look at past orders yet.
- **Ask:** "Which would you value most: (1) 'the usual' product and quantity filled in; (2) 'you usually order cream with this, did you forget it?'; (3) a cheaper product with the same formula; (4) a new or related product? Should a buyer's agent suggest more products at all, or is that Valio's own selling agent?"
- **If there's time:** "Does anything in the data mark a product as new, seasonal or on campaign?"
- **Answer:** everything no? the goal is to provide the best care for our costumers??

**4. Stock covers less than half of the main order**
- **Context:** you told us a buyer asking for milk does not accept coffee milk, so we take it out. That changes our main demo.
- **Example:** 1,000 litres of lactose-free milk by Monday. Confirmed stock now covers 435 litres (two Arla milks, €1,083.39). The other lactose-free milks have stock you don't know, or their deadline has passed. The agent offers the 435 litres, and separately 1,000 litres of Valio Eila whose stock is unknown (€1,010.00). Both go to a person.
- **Ask:** "What would a buyer want here: the 435 confirmed litres now and the rest from a product whose stock isn't confirmed, everything from the unconfirmed product, or to be asked? What happens today when stock covers only part of an order line?"
- **Answer:** the time will keep on going the data is synthetic cant you just pretned you are requesting thrusday or something for monday? 

**5. Payment** (the lowest in priority: ask it last)
- **Context:** your brief names x402 and Nevermined as context. Your website says a credit customer pays by invoice and a "Pay Now" customer pays when ordering. You told us a product sold by weight is invoiced for what is delivered.
- **What we did:** no money moves in our demo. An order is recorded in our own order book. We treat the buyer as a credit customer who is invoiced after delivery.
- **Example:** the hotel orders 30 kg of beef chuck (product 466988) at €16.88 per kg. €506.40 is an estimate; the invoice follows the delivered weight. Nothing is paid when the agent orders.
- **Ask:** "Is 'ordered on a credit account, invoiced after delivery' the right model for our demo, or do you want to see a payment step?"
- **If there's time:** "Does an account have a credit limit an agent's order should be checked against?"
- **Answer:** ________________________________________

**6. What Valio sees in the log**
- **Context:** you said Valio should see all the steps and decisions.
- **Example:** today Valio's view shows every step of an order (9 of 9 events in our main scenario). It does not show which of the buyer's rules fired, the reason, who had to sign, or the products left out for allergen reasons (23 of the ward's 41 exclusions). We plan to show every rule that fired and its outcome, for example "the order is above the buyer's spend limit per order: sent to the buyer's purchasing manager", without the amount (€750), without which allergens the buyer excludes, and with the role instead of the approver's name.
- **Ask:** "Is every decision without the buyer's private values what you meant, or do you want to see those values too?"
- **Answer:** i think the log should show and explain why it made that decision and the logic behind it and product considered

**7. What counts as the same formula?**
- **Context:** you said a substitute or a cheaper item must keep the formula where it matters.
- **Example:** asked for 60 litres of whipping cream (product 469346), the agent today offers 48 litres of it and tops up with 12 litres of a 15% vegetable-fat blend (463975).
- **Ask:** "Is the same brand and product line in another pack size always fine? For another brand, which numbers decide: fat, protein, sugar? Should the agent treat every ingredient as formula-critical unless the buyer says otherwise, or only some product types?"
- **Answer:** you need to consider if the prompt/user is formula dependent like for regular day milk no but for baking/cakes it might be and the contents of the milk might make a diferent based on the chemestry of the product so you really need to consider it get it?

**8. Your data in our public repository** (question 26 of the first list; no answer written)
- **Example:** the submission must be a public repository under the MIT licence. It holds 4 of your data files and the recorded API answers. The README says they are yours and not under the MIT licence.
- **Ask:** "May your data files and the recorded API answers stay in the repository, or should we take them out?"
- **Answer:** ________________________________________

**9. What does a confirmed order fix?** (question 5 of the first list; no answer written)
- **Context:** a person now confirms every order. There is no order endpoint, so "ordered" means recorded in our own order book.
- **Example:** Valio Eila lactose-free milk: price €1.01 valid to 31 Dec, delivery Monday if ordered by Sunday 17:00, stock unknown.
- **Ask:** "When a customer confirms an order with you, what is fixed at that moment: the price, the quantity, the delivery date?"
- **Answer:** ________________________________________

**10. Plain "milk": lactose-free, and mixed fat levels**
- **Context:** a buyer asks for "milk" and names no fat level and no dietary need.
- **Example:** 200 litres of "milk" is answered today with a lactose-free milk drink at €2.48 per litre (product 469363), because regular skimmed milk at €0.88 has no confirmed quantity. And our main demo fills 1,000 litres of lactose-free milk with 384 litres of semi-skimmed plus 51 litres of fat-free.
- **Ask:** "Would a buyer who asks for milk accept a lactose-free milk drink? Is a mix of fat levels fine when the offer says so, or must it be one fat level?"
- **Answer:** what do you think makes the most sense for normal company?

**11. Which order format should we map to?**
- **Context:** our order is our own JSON shape. We want to show how it maps to a standard a wholesaler already receives.
- **Ask:** "Which order format do your customers' systems send you today: Peppol, EDIFACT ORDERS, or only the webshop? Which would your order entry take from a gateway like ours?"
- **Answer:** ________________________________________


we also got information based on what they gave us:

YOU GET :
    pricineg and availability mock APIs
    Product data, delivery reliability and carbon footprint files
    Mentors for AI, wholesale and data governance

GOOD TO KNOW:
    We mock today webshpop, not the marketplce
    it is NOT a chatbot
    Query the APIs only when needed, never for all product

