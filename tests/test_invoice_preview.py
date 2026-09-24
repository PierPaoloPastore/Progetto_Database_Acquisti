"""Anteprima XML tollerante, senza modificare gli originali."""
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from app.services.document_service import render_invoice_html


class InvoicePreviewTests(unittest.TestCase):
    def test_xml_and_p7m_preserve_invoice_data_with_invalid_namespace(self):
        stylesheet = etree.ElementTree(etree.XML(b'''
            <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
              <xsl:template match="/">
                <html><body><xsl:value-of select="//Numero"/>|
                  <xsl:value-of select="//ImportoTotaleDocumento"/>
                </body></html>
              </xsl:template>
            </xsl:stylesheet>
        '''))
        for suffix in ("xml", "p7m"):
            for namespace in (
                b'',
                b' xmlns:schemaLocation="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2 fatturaordinaria_v1.2.xsd"',
            ):
                with self.subTest(suffix=suffix, namespace=namespace):
                    xml = (b'<FatturaElettronica' + namespace + b'>'
                           b'<Numero>FT-123</Numero><ImportoTotaleDocumento>122.50</ImportoTotaleDocumento>'
                           b'</FatturaElettronica>')
                    with (
                        patch.object(Path, "read_bytes", return_value=xml),
                        patch.object(Path, "write_bytes") as write,
                        patch("app.parsers.fatturapa_parser._extract_xml_from_p7m", return_value=xml),
                        patch.object(etree, "parse", return_value=stylesheet) as parse,
                    ):
                        html = render_invoice_html(f"fattura.{suffix}", "style.xsl")
                    self.assertIn("FT-123", html)
                    self.assertIn("122.50", html)
                    write.assert_not_called()
                    parse.assert_called_once_with("style.xsl")

    def test_unreadable_xml_still_raises(self):
        with patch.object(Path, "read_bytes", return_value=b"non e un XML"):
            with self.assertRaises(etree.XMLSyntaxError):
                render_invoice_html("fattura.xml", "style.xsl")


if __name__ == "__main__":
    unittest.main()
