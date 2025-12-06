"""
Test di verifica import modelli dopo migrazione.
"""
try:
    from app.models import Document, RentContract
    print("✅ Document importato con successo")
    print("✅ RentContract importato con successo")

    from app.models import InvoiceLine, VatSummary, Payment
    print("✅ Modelli dipendenti importati con successo")

    # Verifica attributi Document
    assert hasattr(Document, 'document_type')
    assert hasattr(Document, 'supplier_id')
    assert hasattr(Document, 'is_invoice')
    assert hasattr(Document, 'is_f24')
    print("✅ Attributi Document verificati")

    # Verifica FK aggiornate
    assert hasattr(InvoiceLine, 'document_id')
    assert hasattr(Payment, 'document_id')
    print("✅ FK aggiornate verificate")

    print("\n🎉 FASE 1 COMPLETATA CON SUCCESSO!")

except ImportError as e:
    print(f"❌ Errore import: {e}")
except AssertionError as e:
    print(f"❌ Errore verifica: {e}")
except Exception as e:
    print(f"❌ Errore generico: {e}")
