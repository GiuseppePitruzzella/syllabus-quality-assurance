# Revisione documentale e rubrica sperimentale `separated_v1`

Revisione del 14–15 settembre 2026. **Esperimento locale, non modifica della
valutazione in produzione.** Il risultato utile è una rubrica ispezionabile,
con perimetri, esclusioni e soglie complete effettivamente inserite nei prompt.
La validità dei nuovi punteggi resta da calibrare con giudizi umani.

## Documentazione esaminata

Sono stati esaminati i sette documenti del corpus locale che hanno motivato la
rubrica, la progettazione del progetto e i prompt degli agenti. Per i documenti
generali su accreditamento e assicurazione della qualità, l'analisi si concentra
sui passaggi pertinenti alla didattica e ai syllabus.

| Documento nel corpus locale | Passaggi pertinenti | Che cosa giustifica |
|---|---|---|
| Linee guida UniCT per il syllabus, v2.0 (2022, aggiornamento 2023), `lg_unict.md` | §§1–3 e appendici | Informazioni del syllabus, RA, prerequisiti, esami, materiali, didattica e programma |
| Presentazione CPDS UniCT, 24/10/2025, `cpds_unict.md` | Quadri C ed E | Relazione tra risultati e prove; controllo delle informazioni del CdS |
| Matrice di Tuning UniCT, v1.0 gennaio 2026, `matrice_tuning.md` | §§2–3 | Ripartizione dei risultati tra insegnamenti; coerenza con il progetto formativo |
| Linee guida SUA-CdS, v1.1 maggio 2018, `lgsua_cds.md` | A4.b, A4.c e collegamenti alle schede | Risultati dell'intero CdS e loro articolazione |
| Linee guida AVA3, agosto 2024, `ava3.md` | Quadro D.CDS, ruolo CPDS e autovalutazione | Contesto di assicurazione della qualità; non una griglia ufficiale C1–C9 |
| Materiale UniCT AVA3, `ava3_unict.md` | D.CDS.1.2–1.4, in particolare 1.4.1–1.4.2 | Chiarezza dei programmi e delle modalità e dei criteri di verifica |
| DM 1154/2021, `dm1154.md` | Allegato C, ambito D | Quadro di accreditamento; non le nostre soglie numeriche |

Le fonti locali sono conservate nel corpus privato, senza ripubblicarle qui.
Le [impronte delle fonti](rubric-sources-2026-09-15.json) identificano le copie
esaminate, compreso il PDF pubblico 26.04 conservato localmente per la revisione.
Il riferimento attuale è verificabile nell'[elenco ufficiale UniCT](https://www.unict.it/it/ateneo/documenti-e-linee-guida).
La [guida al syllabus ver. 26.04](https://www.unict.it/sites/default/files/files/linee_guida_syllabus.pdf)
è successiva alla copia usata nel corpus. Il §3.1 richiede i due descrittori
disciplinari e consente di aggiungere quelli trasversali, specificando le attività
che li sviluppano. Il §3.7 rende esplicito il collegamento tra didattica e risultati.
Il §3.5 richiede esempi di domande/esercizi. Queste differenze vanno versionate,
senza applicarle retroattivamente come obblighi ai syllabus storici.

La [guida ufficiale alla matrice Tuning](https://www.unict.it/sites/default/files/files/linee_guida_matrice_di_tuning_ver_2026-01_1.pdf)
chiarisce il livello di analisi: i risultati del CdS sono distribuiti tra le attività
formative. Non si può dedurre che ogni insegnamento debba coprirli tutti.

**La scala 0/1/2 e le sue soglie sono decisioni del progetto.** Le fonti
giustificano gli aspetti da osservare; non prescrivono i nove punteggi qui usati.
Neppure le fasce valutative di AVA3 equivalgono direttamente a questa scala.

## Problemi riscontrati

1. **Gli anchor possono sparire dal prompt effettivo.**
   `BaseAgent._criteria_specs()` produce codice e descrizione. I builder usano
   `data.criteria_specs or A*_CRITERIA_SPECS`: una lista non vuota di descrizioni
   sostituisce quindi gli anchor completi. Le fixture storiche presentano questo
   problema. La nuova variante costruisce direttamente le specifiche dal catalogo
   completo e verifica che ogni criterio abbia 0, 1 e 2. Il percorso di produzione
   conserva il comportamento precedente: correggerlo e attivare nuove soglie
   richiede versioni dei prompt e ricalibrazione dedicate.
2. **Requisiti e raccomandazioni si mescolano.** Ore per argomento, ISBN o una
   precisa griglia di voti non sono condizioni universali per il punteggio massimo.
   Gli esami devono comunque essere comprensibili e indicare criteri di giudizio.
3. **C4 confonde il singolo insegnamento con il CdS.** La richiesta incondizionata
   di cinque descrittori è una scelta più restrittiva della guida attuale. Inoltre,
   usare lo stesso laboratorio per più abilità non rende identiche quelle abilità.
   Già la copia locale precedente qualifica i descrittori trasversali con
   “laddove previsti”: l'esigenza di correggere questa interpretazione non nasce
   soltanto dal nuovo documento 2026.
4. **C5 ha usato una distinzione impropria.** Le conoscenze richieste vanno distinte
   dalle propedeuticità formali quando queste sono previste. Non si devono imporre
   sempre due categorie di conoscenze, “culturali” e “disciplinari”.
5. **C8 può confondere mancanza di dati e incoerenza.** Una relazione non verificabile
   non dimostra una contraddizione. La coerenza con il CdS richiede documenti ulteriori.
6. **C9 assorbe difetti di altri criteri.** Inglese e sezioni assenti non sono difetti
   editoriali. Un artefatto del parser non prova un errore nell'originale.

## Regole implementate

Il [catalogo eseguibile](../../backend/app/evaluation/analysis/local_rubric_v1.json)
è la fonte unica dei prompt sperimentali. La tabella riassume le soglie; procedure,
condizioni di applicabilità, campi ed esclusioni sono definiti nel catalogo.

| Criterio | 0 | 1 | 2 |
|---|---|---|---|
| C1 — Copertura informativa | 0–4 sezioni informative su 9 | 5–8 sezioni | Tutte e 9, anche sintetiche |
| C2 — Inglese minimo | Nessuno dei 3 gruppi centrali in inglese | 1–2 gruppi | RA, contenuti e valutazione in inglese |
| C3 — Formulazione dei risultati | Nessun risultato riconoscibile | Risultati presenti, ma almeno uno sostanziale resta generico | Risultati con conoscenze/azioni verificabili e oggetto disciplinare |
| C4 — Domini di apprendimento | Nessun dominio riconoscibile | DD1/DD2 incompleti o indistinti; eventuali domini trasversali non distinguibili o senza attività | DD1 e DD2 distinti; eventuali DD3–5 distinti e sostenuti da attività |
| C5 — Prerequisiti | Informazione assente o inutilizzabile | Indicazioni generiche, soli titoli di corsi o ambiguità formali | Conoscenze comprensibili; requisiti formali distinti se dichiarati; ammessa esplicita assenza di prerequisiti |
| C6 — Trasparenza degli esami | Natura delle prove non identificabile | Prove identificabili, ma svolgimento, criteri o condizioni applicabili incompleti | Prove, svolgimento, criteri e condizioni applicabili comprensibili |
| C7 — Organizzazione del programma | Contenuti non ricostruibili | Ambito comprensibile, struttura generica o assente | Argomenti specifici organizzati in elenco, moduli o progressione |
| C8 — Coerenza interna | Contraddizione documentata su un risultato centrale | Relazione indimostrata o discrepanza circoscritta | Riscontro concreto per RA–contenuti, RA–didattica e RA–esami |
| C9 — Cura editoriale | ≥3 difetti gravi indipendenti in ≥2 campi | Un difetto grave, oppure ≥2 lievi indipendenti in campi diversi | Nessun grave; al massimo un lieve, oppure lievi confinati a un campo |

C1 considera RA, prerequisiti, contenuti, valutazione, esempi, materiali,
didattica, frequenza e programmazione. Le soglie 4/8/9 sono una nuova convenzione
sperimentale, non valori ufficiali. La stessa cautela vale per i conteggi di C9.
L'effetto di queste soglie sui casi di confine deve essere validato da valutatori.

In C8 una componente interamente assente produce **NA per informazioni
insufficienti**, con motivo esplicito. Testo disponibile ma generico conduce
invece a 1 se impedisce di verificare le relazioni. Negli altri criteri, un campo
presente nel payload ma vuoto è un'assenza valutabile. Un dato indispensabile
escluso dal payload è indisponibile: non prova un'omissione nell'originale.

Questa distinzione amplia la semantica storica di NA. La frequenza di NA deve
essere riportata insieme ai punteggi: escludere casi difficili dal denominatore
non deve diventare un modo per far salire artificialmente la qualità media.

## Separazione dei criteri: esempi di confine

| Situazione | Dove valutarla | Effetto da evitare |
|---|---|---|
| Bibliografia assente | C1 | Abbassare automaticamente anche C9 |
| Materiali identificabili costituiti da dispense o progetti | C1: sezione presente | Pretendere necessariamente libri o ISBN |
| RA generici ma divisi in conoscenza e applicazione | C3: formulazione; C4: domini | Dare lo stesso giudizio ai due criteri senza esaminarli |
| Un laboratorio sviluppa giudizio e comunicazione | C4: verificare capacità distinte | Scambiare la stessa attività per la stessa competenza |
| Esame descritto chiaramente ma incompatibile con un RA | C6 può essere alto, C8 basso | Confondere trasparenza e coerenza |
| Programma strutturato, senza ore per argomento | C7 può essere 2 | Inventare un obbligo di pianificazione oraria |
| Inglese assente | C2 | Penalizzarlo nuovamente in C3, C4 o C9 |
| Testo apparentemente troncato dall'estrazione | Verifica tecnica/NA se indispensabile | Attribuire senza prova un errore editoriale al docente |

Sono esempi della nuova politica di valutazione, **non risultati prodotti dal
modello** e non giudizi esperti già validati. I test automatici garantiscono la
costruzione dei prompt, non che Qwen rispetti sempre queste distinzioni.

## Limiti metodologici e promozione

- `separated_v1` cambia sia istruzioni sia alcune regole: in particolare C1, C4,
  C5, C8/NA e C9. Un aumento di accordo con Gemini non isolerebbe un effetto del
  solo prompt e non dimostrerebbe maggiore accuratezza.
- C2 resta un indicatore minimo su tre gruppi, mentre la guida riguarda tutte le
  sezioni. C8 consente di ricostruire le relazioni dal contenuto: non certifica
  l'esplicitazione richiesta dalla guida 26.04. **Non è una verifica completa
  di conformità alla guida 2026.**
- Il contesto RAG storico resta identico ed è marcato come storico. Il catalogo
  sperimentale prevale sulle soglie; il corpus originale non viene aggiornato
  silenziosamente. Una futura campagna sulla guida 2026 richiede un corpus
  coerente e un campione riferito all'anno accademico pertinente.
- C3 e C4 restano correlati, pur avendo domande diverse. Non è giustificato
  modificare pesi o interpretare la somma come una misura scientificamente
  validata senza studiare accordo tra valutatori e ridondanza.
- Il corpus chiuso non sostituisce SUA-CdS, matrice effettiva e regolamento del
  CdS quando si vuole valutare l'allineamento verticale.

La verifica successiva deve usare casi di confine e casi indipendenti annotati
con questa rubrica da valutatori umani, includendo NA e motivazioni. Confrontare
le regole vecchie e nuove su uno stesso campione già usato per modificarle è
una diagnosi, non una validazione indipendente. Tutti i test locali evitano
chiamate Gemini, Vertex, embedding remoti e costi API.

I risultati del primo controllo sul modello sono riportati in
[SEPARATED_RESULTS.md](SEPARATED_RESULTS.md).
