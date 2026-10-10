# OPTIONAL: fetch reference sources outside the committed tree for code audit.
# These are not runtime dependencies, and are deliberately not bundled/distributed.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$refs = @(
 @{ name='atk-logic-official'; url='https://github.com/alientek-openedv/atk-logic.git'; rev='0dff562d24436def2bec3791684f1911997b9e35' },
 @{ name='atk-libsigrokdecode-official'; url='https://github.com/alientek-openedv/atk_libsigrokdecode.git'; rev='783fec96047f5859c2122ac79123a6929a35f75f' },
 @{ name='atk-logic-community-python'; url='https://github.com/hugelzhang/atk-logic-mcp.git'; rev='77320addfb34d3973d09a7af663de76023034587' }
)
foreach($item in $refs) {
 $dst = Join-Path $root ("external\" + $item.name)
 if(-not (Test-Path $dst)) { git clone $item.url $dst; if($LASTEXITCODE -ne 0){throw "Clone failed: $($item.name)"} }
 git -C $dst fetch origin $item.rev
 if($LASTEXITCODE -ne 0){throw "Fetch failed: $($item.name)"}
 git -C $dst checkout --detach $item.rev
 if($LASTEXITCODE -ne 0){throw "Checkout failed: $($item.name)"}
}
Write-Host 'References available in external/ (ignored by git).'
