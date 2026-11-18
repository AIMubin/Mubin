<#
.SYNOPSIS
Review and optionally activate Mubin main branch protection.
.DESCRIPTION
Dry-run by default. -Apply is required for any remote mutation.
Bootstrap creates PR safety without requiring CI contexts not yet on main.
Strict updates only the known bootstrap ruleset after proof that main has
the required workflows and all four exact HEAD check-run jobs succeeded.
This is an operator tool, not evidence of human review or scholarly approval.
#>
[CmdletBinding()]
param(
    [ValidateSet("bootstrap", "strict")]
    [string]$Mode = "bootstrap",
    [switch]$Apply,
    [switch]$IndependentReviewerConfirmed
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Repo = "AIMubin/Mubin"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$Folder = Join-Path $Root "docs/governance"
$TemplateName = if ($Mode -eq "bootstrap") {
    "main-bootstrap.ruleset.json"
} else {
    "main-strict.ruleset.json"
}
$TemplatePath = Join-Path $Folder $TemplateName

function Refuse([string]$Code) {
    throw $Code
}

function GhJson([string]$Endpoint) {
    $Raw = & gh api $Endpoint 2>$null
    if ($LASTEXITCODE -ne 0) {
        Refuse "GITHUB_API_READ_FAILED"
    }
    try {
        return ConvertFrom-Json -InputObject ($Raw -join [Environment]::NewLine) -Depth 64
    } catch {
        Refuse "GITHUB_API_RESPONSE_INVALID"
    }
}

# Check local data even during dry-run. Never treat these templates as a
# substitute for verifying the live GitHub settings after application.
$Template = Get-Content -LiteralPath $TemplatePath -Raw -Encoding UTF8 |
    ConvertFrom-Json -Depth 64
if ($Template.target -ne "branch" -or $Template.enforcement -ne "active" -or
    $Template.conditions.ref_name.include.Count -ne 1 -or
    $Template.conditions.ref_name.include[0] -ne "refs/heads/main" -or
    $Template.bypass_actors.Count -ne 0) {
    Refuse "RULESET_TEMPLATE_SCOPE_INVALID"
}

$PullRules = @($Template.rules | Where-Object { $_.type -eq "pull_request" })
if ($PullRules.Count -ne 1 -or
    -not $PullRules[0].parameters.required_review_thread_resolution) {
    Refuse "RULESET_TEMPLATE_REVIEW_INVALID"
}
$MustPass = @(
    "Baseline contracts and public-preview (ubuntu-latest)",
    "Baseline contracts and public-preview (windows-latest)",
    "Public tracked-artifact safety (ubuntu-latest)",
    "Public tracked-artifact safety (windows-latest)"
)
if ($Mode -eq "bootstrap") {
    if ($PullRules[0].parameters.required_approving_review_count -ne 0 -or
        @($Template.rules | Where-Object {
            $_.type -eq "required_status_checks"
        }).Count -ne 0) {
        Refuse "BOOTSTRAP_MUST_NOT_PREMATURELY_REQUIRE_CHECKS"
    }
} else {
    $StatusRules = @($Template.rules | Where-Object {
        $_.type -eq "required_status_checks"
    })
    if ($StatusRules.Count -ne 1 -or
        $PullRules[0].parameters.required_approving_review_count -lt 1 -or
        -not $PullRules[0].parameters.require_last_push_approval -or
        -not $StatusRules[0].parameters.strict_required_status_checks_policy) {
        Refuse "STRICT_RULESET_WEAKENED"
    }
    $RequiredContexts = @(
        $StatusRules[0].parameters.required_status_checks |
        ForEach-Object { $_.context }
    )
    if ($RequiredContexts.Count -ne $MustPass.Count) {
        Refuse "STRICT_CONTEXTS_MISMATCH"
    }
    foreach ($Context in $MustPass) {
        if ($RequiredContexts -cnotcontains $Context) {
            Refuse "STRICT_CONTEXTS_MISMATCH"
        }
    }
}

if (-not $Apply) {
    Write-Output "DRY_RUN Mode=$Mode Repo=$Repo Template=$TemplateName"
    Write-Output "No GitHub authentication or remote mutation occurred."
    exit 0
}

if ($Mode -eq "strict" -and -not $IndependentReviewerConfirmed) {
    Refuse "INDEPENDENT_REVIEWER_CONFIRMATION_REQUIRED"
}
if ($null -eq (Get-Command gh -ErrorAction SilentlyContinue)) {
    Refuse "GITHUB_CLI_NOT_FOUND"
}
& gh auth status 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Refuse "GITHUB_CLI_AUTH_REQUIRED"
}

$Existing = @(GhJson "repos/$Repo/rulesets?includes_parents=true")
$ExactName = @($Existing | Where-Object { $_.name -eq $Template.name })
if ($ExactName.Count -gt 0) {
    Refuse "TARGET_RULESET_ALREADY_EXISTS_REVIEW_MANUALLY"
}

if ($Mode -eq "bootstrap") {
    & gh api -X POST "repos/$Repo/rulesets" --input $TemplatePath 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        Refuse "BOOTSTRAP_WRITE_FAILED"
    }
    $Branch = GhJson "repos/$Repo/branches/main"
    if (-not $Branch.protected) {
        Refuse "PROTECTION_NOT_CONFIRMED"
    }
    Write-Output "BOOTSTRAP_ACTIVE: GitHub reports main protected; review live rules."
    exit 0
}

$Bootstrap = @($Existing | Where-Object {
    $_.name -eq "Mubin main - bootstrap PR safety"
})
if ($Bootstrap.Count -ne 1) {
    Refuse "VERIFIED_BOOTSTRAP_RULESET_REQUIRED"
}
$RulesetId = [string]$Bootstrap[0].id
if ($RulesetId -notmatch "^[0-9]+$") {
    Refuse "BOOTSTRAP_RULESET_ID_INVALID"
}
$BootstrapDetails = GhJson "repos/$Repo/rulesets/$RulesetId"
$ReferenceList = @($BootstrapDetails.conditions.ref_name.include)
$BootstrapTypes = @($BootstrapDetails.rules | ForEach-Object { $_.type })
if ($BootstrapDetails.target -ne "branch" -or
    $BootstrapDetails.enforcement -ne "active" -or
    $ReferenceList.Count -ne 1 -or
    $ReferenceList[0] -cne "refs/heads/main" -or
    $BootstrapTypes.Count -ne 3 -or
    $BootstrapTypes -ccontains "required_status_checks" -or
    $BootstrapTypes -cnotcontains "pull_request" -or
    $BootstrapTypes -cnotcontains "non_fast_forward" -or
    $BootstrapTypes -cnotcontains "deletion") {
    Refuse "BOOTSTRAP_SCOPE_OR_RULES_MISMATCH"
}
$Branch = GhJson "repos/$Repo/branches/main"
if (-not $Branch.protected) {
    Refuse "PROTECTION_NOT_CONFIRMED"
}
foreach ($Workflow in @("mubin-baseline-guard.yml", "publication-guard.yml")) {
    $Path = "repos/$Repo/contents/.github/workflows/$Workflow" + "?ref=main"
    $Info = GhJson $Path
    if ($Info.type -ne "file") {
        Refuse "MANDATORY_WORKFLOW_NOT_ON_MAIN"
    }
}
$HeadSha = $Branch.commit.sha
if ($HeadSha -notmatch "^[0-9a-f]{40}$") {
    Refuse "MAIN_HEAD_INVALID"
}
$Checks = GhJson "repos/$Repo/commits/$HeadSha/check-runs?per_page=100"
$Passed = @($Checks.check_runs | Where-Object { $_.conclusion -eq "success" } |
    ForEach-Object { $_.name })
foreach ($Context in $MustPass) {
    if ($Passed -cnotcontains $Context) {
        Refuse "REQUIRED_MAIN_HEAD_CHECK_MISSING"
    }
}

# The only allowed update is replacement of our known bootstrap ruleset ID.
# No force push, branch update, manual review spoofing or broad API writes.
& gh api -X PUT "repos/$Repo/rulesets/$RulesetId" --input $TemplatePath 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Refuse "STRICT_RULESET_WRITE_FAILED"
}
$Actual = GhJson "repos/$Repo/rulesets/$RulesetId"
if ($Actual.name -ne $Template.name -or
    $Actual.enforcement -ne "active" -or
    @($Actual.rules | Where-Object {
        $_.type -eq "required_status_checks"
    }).Count -ne 1) {
    Refuse "STRICT_RULESET_NOT_CONFIRMED"
}
Write-Output "STRICT_ACTIVE: review GitHub ruleset and independent approvals."
