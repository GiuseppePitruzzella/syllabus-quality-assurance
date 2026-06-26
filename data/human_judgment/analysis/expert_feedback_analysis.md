# Phase 5.8 — Analisi mirata del feedback esperto

Analisi interamente offline: nessuna chiamata Vertex e nessuna nuova valutazione LLM.

## Completezza del dato umano

- Syllabus nel workbook: 8.
- Syllabus completi: 8.
- Fogli senza punteggi: nessuno.

## C3/C4 — Stessa area, costrutti distinti

- Validation LM-18: n=30, accordo esatto 23/30 (0.767), κ=0.234, MAE=0.233, coppie 2/2=21.
- Self-consistency: n=40, accordo esatto 30/40 (0.750), κ=0.32, MAE=0.25, coppie 2/2=27.

L'accordo esatto è elevato, ma è favorito dall'effetto soffitto: molti syllabus ricevono 2 in entrambi i criteri. Il kappa pesato resta soltanto debole/moderato e sono presenti casi in cui C3 e C4 divergono. I criteri restano quindi separati come sottodimensioni della macro-area Risultati di apprendimento: C3 valuta osservabilità e verificabilità degli outcome; C4 presenza e differenziazione dei cinque Descrittori di Dublino.

## C5 — Requisiti culturali/disciplinari

- Confronto storico A1 a1_v5: n=8, κ=0.0, accuracy=0.5, MAE=0.5.
- Sensibilità con score modale A1 a1_v6: n=8, κ=0.429, accuracy=0.625, MAE=0.375.

Il confronto storico resta valido perché questionario e A1 a1_v5 usavano la stessa regola. La seconda riga misura soltanto quanto cambierebbe l'accordo con la ridefinizione successiva.

## C6 — Difficile per l'uomo, facile per la macchina?

- Accordo dopo micro-rivalutazione C6: n=8, κ=1.0, accuracy=1.0, MAE=0.0.
- Self-consistency C6: unanimità 1.00, stdev media 0.00.

Dopo il follow-up, C6 è confrontabile: il valutatore ha rivisto il criterio usando la definizione di trasparenza delle modalità di verifica. L'accordo perfetto indica che, in questo campione, il criterio è sia stabile per il sistema sia allineato al giudizio esperto; resta comunque un'evidenza diagnostica a singolo valutatore, non una misura di affidabilità inter-rater.

## C7 — Forma discorsiva vs struttura a blocchi

- Confronto osservato: n=8, κ=0.091, accuracy=0.375, MAE=0.625.
- Sensibilità stretta (solo conflitto esplicito blocchi/istruzioni): n=8, κ=0.158, accuracy=0.5, MAE=0.5.
- Categorie delle motivazioni: {'block_or_module_structure': 1, 'insufficient_detail': 1, 'narrative_form': 3, 'no_written_reason': 2, 'other': 1}.

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
