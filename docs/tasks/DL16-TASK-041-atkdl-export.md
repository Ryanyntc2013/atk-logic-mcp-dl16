# DL16-TASK-041 — experimental offline-reader archive writer

Independent ZIP subset writer for known load_atkdl layout,not GUI format parity claim. Public logic_export_atkdl(capture_id,channels,out_name) preserves source/integrity provenance in extra JSON,matching sample rate/depth and LSB-first packed bytes. Partial final byte padded bits masked,exclusive no-overwrite publication. Strict simple filename under exports directory. Native original bits unchanged.

Two offline tests:9sample tail-bit roundtrip,overwrite refusal,mismatched rate rejection. ruff passes. GUI acceptance NOT_RUN because no official GUI file-format/full save schema verification performed;always gui_compatibility UNVERIFIED. Do not label full TASK041 original GUI-compatible criterion complete. Current scope DONE reader-subset writer/provenance,remaining acceptance actual GUI open/channel/time/index comparison requires separately authorized GUI ownership interval.

No USB accessed by export. No vendor proprietary source/DLL bundled. LHX has no .atkdl GUI parity promise;this is original plan extension,not feature inferred from LHX. No source copied. Potential publication failure can leave incomplete destination,not success;caller gets explicit failure and must choose a new name. No automatic overwrite.
