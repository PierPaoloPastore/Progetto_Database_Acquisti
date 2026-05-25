# Internal API Delivery Notes

Endpoint interno per creare DDT provenienti da `GestionaleFitofarmaci`.

## Configurazione

Variabile ambiente richiesta:

```env
INTERNAL_API_TOKEN=imposta-un-token-lungo-e-casuale
```

Il token puo essere inviato in uno dei due modi:

- `Authorization: Bearer <token>`
- `X-Internal-API-Key: <token>`

## Endpoint

`POST /api/internal/delivery-notes`

## Regole applicative

- `document_id = null`
- `status = unmatched`
- `source = manual`
- `import_source = GestionaleFitofarmaci:<external_id>`

## Idempotenza

Prima di creare un nuovo DDT il sistema verifica:

- `supplier_id`
- `ddt_number`
- `ddt_date`
- `import_source`

Se trova un record gia esistente restituisce `200` con:

- `created = false`
- `duplicate = true`

Se crea un nuovo DDT restituisce `201` con:

- `created = true`
- `duplicate = false`

## Formato JSON

```json
{
  "supplier_id": 123,
  "legal_entity_id": 4,
  "ddt_number": "DDT-4587",
  "ddt_date": "2026-05-25",
  "external_id": "fito-2026-0004587",
  "total_amount": "1250.50",
  "notes": "campo accettato ma non persistito nel modello attuale",
  "lines": [
    {
      "line_number": 1,
      "description": "Prodotto fitosanitario X",
      "item_code": "FITO-X",
      "quantity": "10.0000",
      "uom": "pz",
      "amount": "500.00",
      "notes": "lotto 123"
    }
  ]
}
```

## Formato multipart/form-data

Campi:

- `payload`: JSON serializzato
- `file`: PDF o immagine opzionale (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`)

## Errori previsti

- `400` payload non valido
- `401` token mancante o errato
- `404` `supplier_id` o `legal_entity_id` non validi
- `500` errore interno o server non configurato
