"""
Route per il Centro Aiuto con guide operative per nuovi utenti.
"""

from __future__ import annotations

from flask import Blueprint, abort, render_template, url_for

help_bp = Blueprint("help", __name__)


GUIDES: tuple[dict, ...] = (
    {
        "slug": "primo-accesso-e-orientamento",
        "icon": "compass",
        "title": "Primo accesso e orientamento",
        "summary": "Panoramica iniziale delle aree principali del gestionale e del flusso di lavoro consigliato.",
        "audience": "Chi apre il gestionale per la prima volta.",
        "estimated_time": "5 minuti",
        "prerequisites": [
            "Avere accesso al gestionale.",
            "Conoscere almeno il nome del fornitore o del documento da cercare.",
        ],
        "steps": [
            "Apri la dashboard e controlla i riquadri principali: documenti da rivedere, scadenze imminenti e ultime importazioni.",
            "Usa il menu `Documenti` per consultare elenco, revisione e DDT.",
            "Usa il menu `Operazioni` per import, export, pagamenti e scadenziario.",
            "Usa il menu `Anagrafiche` per verificare fornitori, intestazioni e categorie.",
            "Se devi iniziare da un file ricevuto, di solito il percorso corretto e` Import -> Revisione -> Scadenziario/Pagamenti.",
        ],
        "checks": [
            "Sai distinguere dove cercare documenti, dove importarli e dove registrarne il pagamento.",
            "Sai tornare alla dashboard per controllare lo stato generale.",
        ],
        "actions": [
            {"label": "Apri dashboard", "endpoint": "main.index"},
            {"label": "Vai a Documenti da rivedere", "endpoint": "documents.review_list_view"},
        ],
    },
    {
        "slug": "importare-fatture-xml",
        "icon": "cloud-arrow-up",
        "title": "Importare fatture XML/P7M",
        "summary": "Procedura guidata per caricare fatture elettroniche dal proprio PC o da una cartella server.",
        "audience": "Chi deve caricare nuove fatture nel gestionale.",
        "estimated_time": "5-10 minuti",
        "prerequisites": [
            "Avere una cartella con file `.xml` o `.p7m`.",
            "Verificare che i file appartengano al periodo corretto.",
        ],
        "steps": [
            "Apri la pagina Import dal menu `Operazioni`.",
            "Se i file sono sul tuo PC, usa il selettore cartella e scegli la directory da importare.",
            "Se i file sono gia presenti sul server, compila il percorso nel campo dedicato e avvia l'import server.",
            "Attendi il riepilogo finale e controlla quanti file sono stati importati, saltati o segnalati con errore.",
            "Per i file importati correttamente, apri il dettaglio o passa direttamente alla coda `Documenti da rivedere`.",
        ],
        "checks": [
            "Il riepilogo mostra il numero atteso di file importati.",
            "Gli eventuali errori hanno un messaggio leggibile o un report CSV consultabile.",
            "I nuovi documenti compaiono in revisione o nell'elenco documenti.",
        ],
        "actions": [
            {"label": "Apri Import", "endpoint": "import.run_view"},
            {"label": "Apri Revisione", "endpoint": "documents.review_list_view"},
        ],
    },
    {
        "slug": "rivedere-documenti-importati",
        "icon": "clipboard-check",
        "title": "Rivedere documenti importati",
        "summary": "Come controllare i documenti appena entrati, correggere i dati essenziali e chiudere la revisione.",
        "audience": "Chi valida il contenuto delle fatture dopo l'import.",
        "estimated_time": "5 minuti per documento",
        "prerequisites": [
            "Avere gia eseguito un import oppure avere documenti in stato da rivedere.",
        ],
        "steps": [
            "Apri `Documenti da rivedere` dalla dashboard o dal menu `Documenti`.",
            "Filtra la coda se necessario per fornitore, data o stato.",
            "Apri il documento con il pulsante `Rivedi`.",
            "Controlla numero, data, fornitore, intestatario, importi, scadenza e stato della copia fisica.",
            "Salva le correzioni necessarie e passa al documento successivo finche la coda si svuota.",
        ],
        "checks": [
            "Il documento non resta bloccato in stato incoerente.",
            "Le informazioni principali corrispondono al file ricevuto.",
        ],
        "actions": [
            {"label": "Apri coda revisione", "endpoint": "documents.review_list_view"},
            {"label": "Apri elenco documenti", "endpoint": "documents.list_view"},
        ],
    },
    {
        "slug": "registrare-un-pagamento",
        "icon": "cash-coin",
        "title": "Registrare un pagamento",
        "summary": "Flusso base per selezionare uno o piu documenti aperti e registrare il pagamento con PDF e metodo corretto.",
        "audience": "Chi aggiorna i pagamenti effettuati.",
        "estimated_time": "5 minuti",
        "prerequisites": [
            "Avere almeno una fattura aperta o in scadenza.",
            "Avere il PDF del pagamento, se richiesto dal metodo usato.",
        ],
        "steps": [
            "Apri la sezione `Pagamenti` dal menu `Operazioni`.",
            "Passa alla scheda `Nuovo Pagamento`.",
            "Seleziona una o piu fatture dalla lista delle aperte, usando ricerca e filtri se necessario.",
            "Compila data, metodo di pagamento, IBAN e note; allega il PDF quando disponibile o richiesto.",
            "Controlla il riepilogo della selezione e conferma la registrazione del pagamento.",
        ],
        "checks": [
            "Il movimento compare nella cronologia pagamenti.",
            "La fattura risulta aggiornata con importo residuo o stato pagato corretto.",
        ],
        "actions": [
            {"label": "Apri Pagamenti", "endpoint": "payments.payment_index"},
            {"label": "Apri Scadenziario", "endpoint": "payments.schedule_view"},
        ],
    },
    {
        "slug": "consultare-lo-scadenziario",
        "icon": "calendar-check",
        "title": "Consultare lo scadenziario",
        "summary": "Come leggere le scadenze, filtrare i documenti urgenti, preparare la stampa e avviare rapidamente la registrazione pagamento.",
        "audience": "Chi monitora le scadenze da pagare.",
        "estimated_time": "3 minuti",
        "prerequisites": [
            "Avere documenti con scadenza valorizzata.",
        ],
        "steps": [
            "Apri `Scadenziario` dal menu `Operazioni`.",
            "Controlla i riepiloghi in alto per distinguere scadute, imminenti e totale da pagare.",
            "Usa ricerca, filtri per data o stato e selezione dei documenti per isolare il gruppo da lavorare.",
            "Se devi condividere o preparare una lista di pagamento, seleziona i documenti e usa la barra azioni per stampare il PDF.",
            "Apri il dettaglio del documento per verifiche puntuali oppure usa `Registra` per passare subito al pagamento.",
        ],
        "checks": [
            "Sai individuare subito le fatture scadute e quelle da pagare a breve.",
            "Sai distinguere tra semplice consultazione, stampa di una lista e registrazione effettiva del pagamento.",
            "Riesci a passare dallo scadenziario alla registrazione pagamento senza cercare manualmente il documento.",
        ],
        "actions": [
            {"label": "Apri Scadenziario", "endpoint": "payments.schedule_view"},
            {"label": "Guida stampa estratti conto", "endpoint": "help.guide_view", "params": {"slug": "stampare-estratti-conto-dallo-scadenziario"}},
            {"label": "Apri Pagamenti", "endpoint": "payments.payment_index"},
        ],
    },
    {
        "slug": "stampare-estratti-conto-dallo-scadenziario",
        "icon": "printer",
        "title": "Stampare estratti conto dallo scadenziario",
        "summary": "Come selezionare le fatture da includere nel PDF dello scadenziario e come interpretare il risultato della stampa.",
        "audience": "Chi prepara liste di pagamento o riepiloghi da condividere e controllare.",
        "estimated_time": "3-5 minuti",
        "prerequisites": [
            "Avere documenti visibili nello scadenziario.",
            "Avere wkhtmltopdf o WeasyPrint configurato se la stampa PDF e` abilitata nell'ambiente.",
        ],
        "steps": [
            "Apri `Scadenziario` dal menu `Operazioni`.",
            "Filtra l'elenco per data, stato, importo o intestatario fino a isolare le fatture che vuoi includere nell'estratto.",
            "Seleziona una o piu righe con le checkbox nella tabella oppure usa la selezione dei visibili.",
            "Quando compare la barra azioni, usa `Stampa come PDF`.",
            "Il gestionale genera un PDF con scadenza, fornitore, IBAN fornitore, intestatario, numero documento, totale, residuo e stato della scadenza.",
            "Dopo la stampa i documenti selezionati vengono marcati come `Programmata`, cosi puoi riconoscere che sono gia entrati in una lista di pagamento.",
            "Se la marcatura non serve piu, seleziona di nuovo i documenti e usa `Togli programmata`.",
        ],
        "checks": [
            "Il PDF contiene solo i documenti che avevi selezionato.",
            "Lo stato `Programmata` compare sulle righe gia inserite in una stampa.",
            "Sai che la stampa non registra il pagamento: crea solo un riepilogo PDF e imposta il flag di programmazione.",
        ],
        "actions": [
            {"label": "Apri Scadenziario", "endpoint": "payments.schedule_view"},
            {"label": "Apri Pagamenti", "endpoint": "payments.payment_index"},
        ],
    },
    {
        "slug": "cercare-documenti-e-usare-i-filtri",
        "icon": "funnel",
        "title": "Cercare documenti e usare i filtri",
        "summary": "Procedura rapida per trovare un documento per numero, fornitore, periodo, stato o importo.",
        "audience": "Chi deve recuperare rapidamente fatture gia presenti.",
        "estimated_time": "2-3 minuti",
        "prerequisites": [
            "Avere almeno un riferimento: numero documento, fornitore, data o stato.",
        ],
        "steps": [
            "Apri `Elenco documenti` dal menu `Documenti`.",
            "Usa il campo di ricerca libera per numero, fornitore o testo principale.",
            "Apri i filtri avanzati per restringere per periodo, intestatario, stato pagamento o importo.",
            "Controlla i chip dei filtri attivi per capire subito quali vincoli stai applicando.",
            "Apri il dettaglio del documento trovato per verifiche o azioni successive.",
        ],
        "checks": [
            "Sai azzerare i filtri e ripartire da una ricerca pulita.",
            "Riesci a trovare un documento anche senza conoscere l'ID interno.",
        ],
        "actions": [
            {"label": "Apri elenco documenti", "endpoint": "documents.list_view"},
            {"label": "Apri Fornitori", "endpoint": "suppliers.list_view"},
        ],
    },
)


def _find_guide(slug: str) -> dict | None:
    return next((guide for guide in GUIDES if guide["slug"] == slug), None)


def _build_action_links(guide: dict) -> list[dict]:
    action_links: list[dict] = []
    for action in guide.get("actions", []):
        params = action.get("params", {})
        action_links.append(
            {
                "label": action["label"],
                "href": url_for(action["endpoint"], **params),
            }
        )
    return action_links


@help_bp.route("/help")
def index():
    guides = []
    for guide in GUIDES:
        guides.append(
            {
                **guide,
                "href": url_for("help.guide_view", slug=guide["slug"]),
                "action_links": _build_action_links(guide),
            }
        )
    return render_template("help/index.html", guides=guides)


@help_bp.route("/help/<slug>")
def guide_view(slug: str):
    guide = _find_guide(slug)
    if guide is None:
        abort(404)

    related_guides = [
        {
            "title": item["title"],
            "summary": item["summary"],
            "href": url_for("help.guide_view", slug=item["slug"]),
        }
        for item in GUIDES
        if item["slug"] != slug
    ][:3]

    return render_template(
        "help/guide.html",
        guide={**guide, "action_links": _build_action_links(guide)},
        related_guides=related_guides,
    )
