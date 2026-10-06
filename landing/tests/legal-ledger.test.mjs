import test from 'node:test';
import assert from 'node:assert/strict';
import {legalLedger} from '../src/legalLedger.js';

test('draft ledger retains exact supplied passages, versions and review warnings', () => {
  const source = {citation_id:'L1',title:'SYNTHETIC source',pinpoint:'Rn. 7',url:'https://example.invalid/fixture',fetched_at:'2026-10-06T00:00:00Z',metadata:{decision_type:'SYNTHETIC',decision_date:'2026-10-01',reference:'TEST 999',ecli:'TEST-ECLI'},review_status:'pending',review_note:'SYNTHETIC review note',text:'Exact excerpt with ü and line\ncontinuation.',excerpt_truncated:true,source_sha256:'source-hash',excerpt_sha256:'excerpt-hash'};
  for (const lang of ['de','en']) {
    const ledger = legalLedger([source],{unknown:['L99'],missing_citations:true},lang);
    for (const value of [source.text,source.url,source.fetched_at,source.review_note,source.source_sha256,source.excerpt_sha256,source.metadata.reference,source.metadata.ecli,'[L1]','L99']) assert.ok(ledger.includes(value),value);
    assert.match(ledger,/PRÜFUNG ERFORDERLICH|REVIEW REQUIRED/);
    assert.match(ledger,/keine zugeordneten Quellenverweise|no matched source references/);
  }
});

test('unsupported citation warnings survive adoption even without supplied sources', () => {
  assert.equal(legalLedger(), '');
  assert.match(legalLedger([],{unknown:['L99']},'en'),/Unmatched AI references: L99/);
});
