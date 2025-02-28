# 📊 Analys av Boxplottar

## **Boxplott 1: Laddningsenergi per veckodag**
### 🔹 **Generell form & spridning**
- Medianladdningsenergin (tjock linje i varje låda) är relativt **konstant över alla veckodagar**, vilket tyder på att det inte finns någon stark veckovis trend.
- **Interkvartilavståndet (IQR)** (de mittersta 50 % av datan) är också liknande för både vardagar och helger.
- Det finns **outliers under alla dagar**, där extrema värden når upp till **1 000 000 Wh**.

### 🔹 **Outliers & variationer**
- **Torsdag och söndag verkar ha den bredaste spridningen av outliers**, vilket kan indikera oregelbunden toppanvändning dessa dagar.
- De långa "mustascherna" visar att det finns **stor variation i energiförbrukning** över alla veckodagar.
- Det finns **ingen tydlig minskning av medianvärdet under helgerna**, vilket antyder att laddningsbeteendet är ganska stabilt mellan vardagar och helger.

### 🔹 **Säsongens påverkan**
- De färgkodade säsongsfördelningarna visar att **alla säsonger är jämnt fördelade över veckodagarna**.
- Det finns **ingen stark säsongsberoende trend**, vilket tyder på att energiförbrukningens fluktuationer beror mer på andra faktorer än årstiden.

---

## **Boxplott 2: Laddningsenergi per timme på dygnet**
### 🔹 **Timvisa trender i energiförbrukning**
- Det finns ett **tydligt mönster i energianvändningen under dygnet**:
  - **Högre variation under sena nätter och tidiga morgontimmar (0-6 AM).**
  - **Mer stabil energiförbrukning mellan 07:00 och 22:00 (dagtid och kvällstid).**
  - **En tydlig ökning i medianvärdet på eftermiddagen (16:00–21:00).**
- Tidiga morgontimmar (**4–6 AM**) visar ett intressant beteende, med **högre medianförbrukning jämfört med senare på morgonen**.

### 🔹 **Outliers & toppanvändningstider**
- **Extrema outliers syns främst runt 9:00 och 18:00–20:00**, vilket kan bero på:
  - **Morgonpendling** (folk laddar efter att ha kommit till jobbet).
  - **Kvällstopp (folk laddar bilen efter att ha kommit hem).**
- **Variationen i laddningsmängd är större under icke-peak timmar (midnatt till tidig morgon)**, med vissa extrema fall av mycket hög energiförbrukning.

### 🔹 **Säsongens påverkan på timanvändning**
- Den säsongsmässiga färgfördelningen är **relativt jämn över dygnet**, vilket innebär att säsongsförändringar **inte har en stark påverkan på laddningsvanor vid olika tider på dygnet**.
- Dock syns **en liten ökning av gröna boxar (möjligen vinter) under tidiga morgontimmar**, vilket kan antyda att fler laddar sina fordon över natten på grund av kallare temperaturer.

---

## **🔑 Nyckelinsikter & Hypoteser**
1. **Energiförbrukningen är relativt stabil över hela veckan**, med inga stora skillnader mellan vardagar och helger.
2. **Laddningsbeteende varierar mer beroende på tid på dygnet än veckodag.**
3. **Outliers förekommer genomgående, men toppanvändning sker främst tidigt på morgonen och på kvällen.**
4. **Det finns ett tydligt mönster där laddning tenderar att toppa runt 9:00 och 18:00–20:00, vilket sammanfaller med pendlingsmönster.**
5. **Säsong påverkar inte laddningsmönstret signifikant, men vissa trender i tidiga morgontimmar kan indikera vinterrelaterad laddning.**

---

## **📝 Slutsats**
Boxplottarna visar att **laddningsbeteendet påverkas mer av tid på dygnet än av veckodag eller säsong.**  
Morgon- och kvällstoppar överensstämmer med **pendlingsvanor, medan hög variation nattetid kan bero på individuell laddningsstrategi.**  

