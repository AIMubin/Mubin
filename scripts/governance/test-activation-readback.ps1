# Offline adversarial tests for governance activation's read-back gates.
# Mock gh is a PowerShell function: no network, vault or real credentials.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$Activation = Join-Path $PSScriptRoot "activate-main-ruleset.ps1"
$BootstrapPath = Join-Path $Root "docs/governance/main-bootstrap.ruleset.json"
$global:Writes = 0
$global:Scenario = "bootstrap-bypass"

function global:gh {
    $Call = ($args -join " ")
    $global:LASTEXITCODE = 0
    if ($Call -eq "auth status") { return }
    if ($Call -eq "api repos/AIMubin/Mubin/rulesets?includes_parents=true") {
        if ($global:Scenario -eq "bootstrap-bypass" -and
            $global:Writes -eq 0) {
            return "[]"
        }
        return '[{"name":"Mubin main - bootstrap PR safety","id":12345}]'
    }
    if ($Call -eq "api repos/AIMubin/Mubin/rulesets/12345") {
        $Policy = Get-Content -LiteralPath $BootstrapPath -Raw -Encoding UTF8 |
            ConvertFrom-Json -Depth 64
        $Policy | Add-Member -NotePropertyName "id" -NotePropertyValue 12345
        if ($global:Scenario -eq "bootstrap-bypass") {
            $Policy.bypass_actors = @(
                @{ actor_id = 1; actor_type = "OrganizationAdmin"; bypass_mode = "always" }
            )
        } elseif ($global:Scenario -eq "strict-missing-force-push") {
            $Policy.rules = @($Policy.rules | Where-Object {
                $_.type -ne "non_fast_forward"
            })
        }
        return (ConvertTo-Json -InputObject $Policy -Depth 64 -Compress)
    }
    if ($Call -like "api -X POST repos/AIMubin/Mubin/rulesets*") {
        $global:Writes += 1
        return '{"id":12345}'
    }
    if ($Call -like "api -X PUT repos/AIMubin/Mubin/rulesets*") {
        $global:Writes += 1
        return '{"id":12345}'
    }
    if ($Call -eq "api repos/AIMubin/Mubin/branches/main") {
        return ('{"protected":true,"commit":{"sha":"' + ('a' * 40) + '"}}')
    }
    throw "UNEXPECTED_FAKE_GITHUB_CALL"
}

function ExpectRefusal([string]$Expected, [scriptblock]$Action) {
    $Caught = $null
    try {
        & $Action | Out-Null
    } catch {
        $Caught = $_.Exception.Message
    }
    if ($Caught -cne $Expected) {
        throw "MOCK_REFUSAL_MISMATCH expected=$Expected actual=$Caught"
    }
}

# The mock POST must not be called successful if a bypass actor appears
# in the API read-back; the POST is simulated, never sent to GitHub.
ExpectRefusal "RULESET_REMOTE_BYPASS_DETECTED" {
    & $Activation -Mode bootstrap -Apply
}
if ($global:Writes -ne 1) {
    throw "BOOTSTRAP_MOCK_POST_COUNT_INVALID"
}

# A preexisting weakened bootstrap must block strict PUT before any write.
$global:Writes = 0
$global:Scenario = "strict-missing-force-push"
ExpectRefusal "RULESET_REMOTE_RULES_MISMATCH" {
    & $Activation -Mode strict -Apply -IndependentReviewerConfirmed
}
if ($global:Writes -ne 0) {
    throw "STRICT_MOCK_UNEXPECTED_WRITE"
}
Write-Output "MOCK_READBACK_NEGATIVES_PASS no_network=true"
