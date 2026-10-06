import json
import unittest
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app as api, legal_catalogue as catalogue
from server.legal_context import citation_audit

LAW_XML = b'''<?xml version="1.0"?><!DOCTYPE dokumente SYSTEM "https://www.gesetze-im-internet.de/dtd/test.dtd"><dokumente builddate="20261006"><norm doknr="HEADER"><metadaten><jurabk>BGB</jurabk><langue>SYNTHETIC STATUTE</langue><standangabe><standkommentar>SYNTHETIC VERSION ONE</standkommentar></standangabe></metadaten></norm><norm doknr="TEST535"><metadaten><enbez>\xc2\xa7 535</enbez><titel>SYNTHETIC RENTAL FIXTURE</titel></metadaten><textdaten><text><Content><P>(1) SYNTHETIC OBLIGATION ONE.</P><P>(2) SYNTHETIC OBLIGATION TWO.</P></Content></text></textdaten></norm></dokumente>'''
INDEX_XML = b'''<items><item><gericht>BGH 8. Zivilsenat</gericht><entsch-datum>20261001</entsch-datum><aktenzeichen>VIII ZR 999/26</aktenzeichen><link>http://www.rechtsprechung-im-internet.de/jportal/docs/bsjrs/jb-TEST999.zip</link><modified>2026-10-06</modified></item></items>'''
DECISION_XML = b'''<dokument><doknr>TEST999</doknr><gertyp>BGH</gertyp><entsch-datum>20261001</entsch-datum><aktenzeichen>VIII ZR 999/26</aktenzeichen><doktyp>Urteil</doktyp><ecli>SYNTHETIC-ECLI</ecli><gruende><div><dl><dt><a>7</a></dt><dd><p>SYNTHETIC RENTAL REASON ONLY.</p></dd></dl></div></gruende></dokument>'''


class LegalResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.paths = api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH,catalogue.LEGAL_DIR
        api.DATA_DIR = Path(self.temp.name)
        api.UPLOAD_DIR = api.DATA_DIR / 'uploads'
        api.DB_PATH = api.DATA_DIR / 'app.db'
        catalogue.LEGAL_DIR = api.DATA_DIR / 'public-catalogue'
        api.failed_logins.clear()
        catalogue.init_catalogue()
        catalogue.store_rows(catalogue.parse_law(LAW_XML,'bgb'),'law:bgb')
        catalogue.store_rows(catalogue.parse_decision_index(INDEX_XML),'decision-index')

    def tearDown(self):
        api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH,catalogue.LEGAL_DIR = self.paths
        self.temp.cleanup()

    def register(self, client, email='source-test@example.invalid'):
        client.headers['X-Schimmelpilz-Request'] = '1'
        payload = dict(email=email,password='Synthetic-legal-sources-2026!',audience='consumer',full_name='Example Person',street='Example 1',postal_code='10115',city='Berlin',country='Deutschland')
        result = client.post('/api/auth/register',json=payload)
        if result.status_code == 409:
            result = client.post('/api/auth/login',json={'email':email,'password':payload['password']})
        self.assertIn(result.status_code,[200,201],result.text)

    def case(self,client,jurisdiction='DE'):
        return client.post('/api/cases',json={'title':'Synthetic rental research','description':'Only synthetic test data, no client particulars.','details':{'jurisdiction':jurisdiction}}).json()['id']

    def test_official_adapters_reject_external_urls_entities_and_identity_mismatch(self):
        for url in ['https://localhost/bgb/xml.zip','http://127.0.0.1/rii-toc.xml','https://www.gesetze-im-internet.de.evil.test/bgb/xml.zip','https://www.gesetze-im-internet.de:8443/bgb/xml.zip','https://www.gesetze-im-internet.de/bgb/xml.zip?private=query','file:///example']:
            with self.assertRaises(ValueError):
                catalogue.safe_url(url)
        self.assertEqual(catalogue.safe_url('http://www.gesetze-im-internet.de/bgb/xml.zip'),catalogue.GII+'/bgb/xml.zip')
        with self.assertRaises(ValueError):
            catalogue.xml_root(b'<!DOCTYPE x [<!ENTITY a "bad">]><x/>')
        expected = catalogue.parse_decision_index(INDEX_XML)[0]
        parsed = catalogue.parse_decision(DECISION_XML,expected)
        self.assertEqual(parsed['units'][0]['pinpoint'],'Rn. 7')
        self.assertEqual(parsed['metadata']['decision_type'],'Urteil')
        for altered in [DECISION_XML.replace(b'TEST999',b'TEST888'),DECISION_XML.replace(b'20261001',b'20260930'),DECISION_XML.replace(b'VIII ZR 999/26',b'VIII ZR 998/26')]:
            with self.assertRaises(ValueError):
                catalogue.parse_decision(altered,expected)

    def test_local_search_updates_without_duplicate_or_removed_provisions(self):
        self.assertEqual(len(catalogue.search('535 BGB','law')),1)
        catalogue.store_rows(catalogue.parse_law(LAW_XML.replace(b'ONE',b'REVISED'),'bgb'),'law:bgb')
        self.assertEqual(len(catalogue.search('535 BGB','law')),1)
        self.assertNotIn(' OBLIGATION ONE.',catalogue.source('law:bgb:TEST535')['text'])
        other = catalogue.parse_law(LAW_XML.replace(b'TEST535',b'TEST536').replace(b'535',b'536'),'bgb')
        catalogue.store_rows(other,'law:bgb')
        with self.assertRaises(LookupError):
            catalogue.source('law:bgb:TEST535')

    def test_failed_fetch_and_sync_preserve_prior_content_and_report_failure(self):
        original = catalogue.source('law:bgb:TEST535')
        with patch.object(catalogue,'LAWS',{'bgb':'BGB'}),patch.object(catalogue,'fetch_public',side_effect=OSError('offline')):
            catalogue.sync_catalogue(decisions_per_court=0)
        self.assertEqual(catalogue.source('law:bgb:TEST535')['sha256'],original['sha256'])
        self.assertIn('BGB',catalogue.catalogue_status()['progress']['errors'])
        with patch.object(catalogue,'fetch_public',side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                catalogue.source('decision:TEST999')
        self.assertEqual(catalogue.search('VIII ZR 999/26','decision')[0]['origin_status'],'index_only')

    def test_source_write_waits_for_concurrent_catalogue_transaction(self):
        started = threading.Event()
        original_database = catalogue.database
        @contextmanager
        def observed_database():
            with original_database() as db:
                started.set()
                yield db
        rows = catalogue.parse_law(LAW_XML.replace(b'ONE',b'AFTER-REFRESH'),'bgb')
        with original_database() as writer, ThreadPoolExecutor(max_workers=1) as pool:
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE entries SET listed_at='refresh-in-progress' WHERE key='law:bgb:TEST535'")
            with patch.object(catalogue,'database',observed_database):
                pending = pool.submit(catalogue.store_rows,rows)
                self.assertTrue(started.wait(5))
                writer.commit()
                pending.result(timeout=5)
        self.assertIn('AFTER-REFRESH',catalogue.source('law:bgb:TEST535')['text'])
        self.assertEqual(len(catalogue.search('535 BGB','law')),1)

    def test_index_migration_preserves_sources_and_aligns_fts_rowids(self):
        original = catalogue.source('law:bgb:TEST535')
        with catalogue.database() as db:
            db.execute("DELETE FROM catalogue_state WHERE key='fts_rowid_version'")
            db.execute('DELETE FROM entry_search')
            db.execute("INSERT INTO entry_search(rowid,key,title,text) VALUES(99999,'obsolete','obsolete','obsolete')")
        catalogue.INITIALIZED.discard((catalogue.LEGAL_DIR / 'catalogue.db').resolve())
        catalogue.init_catalogue()
        with catalogue.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM entry_search s JOIN entries e ON s.rowid=e.rowid AND s.key=e.key').fetchone()[0],2)
        self.assertEqual(catalogue.source('law:bgb:TEST535')['sha256'],original['sha256'])
        self.assertEqual(len(catalogue.search('535 BGB','law')),1)

    def test_case_source_reviews_generation_provenance_isolation_and_idempotence(self):
        with TestClient(api.app) as client:
            self.register(client)
            case,other = self.case(client),self.case(client)
            attached = client.post(f'/api/cases/{case}/legal-sources',json={'key':'law:bgb:TEST535'}).json()
            identifier = attached['id']
            review = f'/api/cases/{case}/legal-sources/{identifier}/review'
            self.assertEqual(client.put(review,json={'status':'checked','note':'short'}).status_code,422)
            self.assertEqual(client.put(review,json={'status':'checked','note':'SYNTHETIC VERSION and passage relevance checked for TEST ONLY.'}).status_code,200)
            self.assertEqual(client.put(f'/api/cases/{other}/legal-sources/{identifier}/review',json={'status':'excluded'}).status_code,404)
            payload = {'request_id':str(uuid.uuid4()),'question':'Explain the synthetic obligation.','language':'en','legal_source_ids':[identifier]}
            result = {'answer':'Synthetic obligation [L1]. Invented ID [L99].','input_tokens':12,'output_tokens':20,'truncated':False}
            with patch.object(api,'generate_answer',return_value=result) as model:
                run = client.post(f'/api/cases/{case}/research',json=payload)
                self.assertEqual(run.status_code,201,run.text)
                run = run.json()
                self.assertEqual(run['citation_audit']['unknown'],['L99'])
                self.assertEqual(run['citation_audit']['matched'],['L1'])
                self.assertEqual(run['legal_sources'][0]['review_status'],'checked')
                self.assertIn('SYNTHETIC OBLIGATION ONE',str(model.call_args.args[0]))
                catalogue.store_rows(catalogue.parse_law(LAW_XML.replace(b'ONE',b'CHANGED'),'bgb'),'law:bgb')
                new_attachment = client.post(f'/api/cases/{case}/legal-sources',json={'key':'law:bgb:TEST535'}).json()
                self.assertNotEqual(new_attachment['id'],identifier)
                client.put(review,json={'status':'excluded','note':'Later review excluded it.'})
                repeated = client.post(f'/api/cases/{case}/research',json=payload)
                self.assertEqual(repeated.json()['legal_sources'],run['legal_sources'])
                self.assertEqual(model.call_count,1)
                self.assertEqual(client.post(f'/api/cases/{case}/research',json={**payload,'use_legal_catalogue':True}).status_code,409)
                self.assertEqual(client.post(f'/api/cases/{case}/research',json={**payload,'request_id':str(uuid.uuid4())}).status_code,422)
                self.assertEqual(client.post(f'/api/cases/{other}/research',json={**payload,'request_id':str(uuid.uuid4())}).status_code,404)
                self.register(client,'other-source-account@example.invalid')
                self.assertEqual(client.get(f'/api/cases/{case}/legal-sources').status_code,404)
                self.assertEqual(client.put(review,json={'status':'pending'}).status_code,404)
        with TestClient(api.app) as client:
            self.register(client)
            history = client.get(f'/api/cases/{case}/research').json()
            self.assertEqual(history[0]['legal_sources'],run['legal_sources'])
            self.assertEqual(history[0]['legal_sources'][0]['review_status'],'checked')

    def test_automatic_retrieval_is_local_and_jurisdiction_scoped(self):
        with TestClient(api.app) as client:
            self.register(client)
            case,mexico = self.case(client),self.case(client,'MX')
            payload = {'request_id':str(uuid.uuid4()),'question':'535 BGB','use_legal_catalogue':True}
            with patch.object(catalogue,'fetch_public',side_effect=AssertionError('Private question must not be transmitted')),patch.object(api,'generate_answer',return_value={'answer':'Example without any citation.','input_tokens':1,'output_tokens':1,'truncated':False}):
                run = client.post(f'/api/cases/{case}/research',json=payload)
                self.assertEqual(run.status_code,201,run.text)
                self.assertTrue(run.json()['legal_sources'])
                self.assertTrue(run.json()['citation_audit']['missing_citations'])
                self.assertEqual(client.post(f'/api/cases/{mexico}/research',json={**payload,'request_id':str(uuid.uuid4())}).status_code,422)
        self.assertEqual(citation_audit('Nothing supplied [L2]',[])['unknown'],['L2'])


if __name__ == '__main__':
    unittest.main()
