# Phase 5.8 — Analisi mirata del feedback esperto

Analisi interamente offline: nessuna chiamata Vertex e nessuna nuova valutazione LLM.

## Completezza del dato umano

- Syllabus nel workbook: 8.
- Syllabus completi: 7.
- Fogli senza punteggi: 08_VULN_ASSESSMENT_PT.

## C3/C4 — Stessa area, costrutti distinti

- Validation LM-18: n=30, accordo esatto 23/30 (0.767), κ=0.234, MAE=0.233, coppie 2/2=21.
- Self-consistency: n=40, accordo esatto 30/40 (0.750), κ=0.32, MAE=0.25, coppie 2/2=27.

L'accordo esatto è elevato, ma è favorito dall'effetto soffitto: molti syllabus ricevono 2 in entrambi i criteri. Il kappa pesato resta soltanto debole/moderato e sono presenti casi in cui C3 e C4 divergono. I criteri restano quindi separati come sottodimensioni della macro-area Risultati di apprendimento: C3 valuta osservabilità e verificabilità degli outcome; C4 presenza e differenziazione dei cinque Descrittori di Dublino.

## C5 — Requisiti culturali/disciplinari

- Confronto storico A1 a1_v5: n=7, κ=0.0, accuracy=0.571, MAE=0.429.
- Sensibilità con score modale A1 a1_v6: n=7, κ=0.276, accuracy=0.571, MAE=0.429.

Il confronto storico resta valido perché questionario e A1 a1_v5 usavano la stessa regola. La seconda riga misura soltanto quanto cambierebbe l'accordo con la ridefinizione successiva.

## C6 — Difficile per l'uomo, facile per la macchina?

- Accordo numerico non interpretabile: n=7, κ=-0.312, accuracy=0.143, MAE=0.857.
- Self-consistency C6: unanimità 1.00, stdev media 0.00.

C6 è stabile per la macchina, ma il questionario umano misurava un altro costrutto. Non è possibile concludere che la macchina sia più brava finché l'esperto non valuta la trasparenza della verifica.

## C7 — Forma discorsiva vs struttura a blocchi

- Confronto osservato: n=7, κ=0.054, accuracy=0.286, MAE=0.714.
- Sensibilità stretta (solo conflitto esplicito blocchi/istruzioni): n=7, κ=0.125, accuracy=0.429, MAE=0.571.
- Categorie delle motivazioni: {'block_or_module_structure': 1, 'insufficient_detail': 1, 'narrative_form': 3, 'no_written_reason': 1, 'other': 1}.

## Checklist locale LM-18 sui 30 syllabus

| Controllo | Presenti | Totale |
| --- | ---: | ---: |
| Clausola modalità mista/distanza | 28 | 30 |
| Clausola CInAP/DSA | 26 | 30 |
| Clausola verifica telematica | 23 | 30 |
| Griglia completa delle fasce di voto | 16 | 30 |
| Programmazione presente | 29 | 30 |
| Programmazione con tutti gli argomenti | 29 | 30 |
| Programmazione con almeno un riferimento | 28 | 30 |
| Programmazione con riferimenti in tutte le righe | 27 | 30 |

### Syllabus che non soddisfano ciascun controllo

- **Clausola modalità mista/distanza:** `B99A46CC` COMPUTER VISION E LABORATORIO, `0B53E8E2` INTERNET OF THINGS.
- **Clausola CInAP/DSA:** `89E21813` COMPUTER VISION, `1408B85C` Deep Learning, `0B53E8E2` INTERNET OF THINGS, `D5CD7C87` MULTIMEDIA E LABORATORIO.
- **Clausola verifica telematica:** `3ED4B3BB` Advanced Computer Graphics, `B99A46CC` COMPUTER VISION E LABORATORIO, `0B53E8E2` INTERNET OF THINGS, `E2446DF6` OTTIMIZZAZIONE, `C6F1C332` PEER TO PEER AND WIRELESS NETWORKS E LABORATORIO, `F4AF1512` PEER TO PEER AND WIRELESS NETWORKS E LABORATORIO, `71D7A8F2` QUANTUM COMPUTER PROGRAMMING.
- **Griglia completa:** `AC75068C` BLOCKCHAIN E CRYPTOCURRENCIES, `F8F95848` BLOCKCHAIN E CRYPTOCURRENCIES, `89E21813` COMPUTER VISION, `DADC30FD` CRITTOGRAFIA, `AE4C5A2B` CRYPTOGRAPHIC ENGINEERING, `9A85B8E4` INGEGNERIA DEI SISTEMI DISTRIBUITI E LABORATORIO, `CE3B947A` INGEGNERIA DEI SISTEMI DISTRIBUITI E LABORATORIO, `0B53E8E2` INTERNET OF THINGS, `FE97232C` MACHINE LEARNING, `D5CD7C87` MULTIMEDIA E LABORATORIO, `C6F1C332` PEER TO PEER AND WIRELESS NETWORKS E LABORATORIO, `F4AF1512` PEER TO PEER AND WIRELESS NETWORKS E LABORATORIO, `EEA0EC5A` SISTEMI CLOUD E LABORATORIO, `27066AED` Sistemi Cloud.
- **Programmazione presente:** `3ED4B3BB` Advanced Computer Graphics.
- **Programmazione con tutti gli argomenti:** `3ED4B3BB` Advanced Computer Graphics.
- **Programmazione con almeno un riferimento:** `3ED4B3BB` Advanced Computer Graphics, `0B53E8E2` INTERNET OF THINGS.
- **Programmazione con riferimenti in tutte le righe:** `3ED4B3BB` Advanced Computer Graphics, `0B53E8E2` INTERNET OF THINGS, `27066AED` Sistemi Cloud.

Questi controlli sono requisiti locali configurabili, non nuovi criteri core. La tabella completa per syllabus è disponibile nel JSON associato.
