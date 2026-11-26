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
# Verified on both baseline #142 and publication #146 check-runs.
$TrustedChecksAppId = 15368
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

# Fail closed on both local template policy regression and API read-back drift.
function ConfirmRulesetMatches($Expected, $Actual) {
    if ($Actual.target -ne $Expected.target -or
        $Actual.enforcement -ne $Expected.enforcement) {
        Refuse "RULESET_REMOTE_SCOPE_MISMATCH"
    }
    if (@($Actual.bypass_actors).Count -ne 0) {
        Refuse "RULESET_REMOTE_BYPASS_DETECTED"
    }
    $Included = @($Actual.conditions.ref_name.include)
    if ($Included.Count -ne 1 -or $Included[0] -cne "refs/heads/main" -or
        @($Actual.conditions.ref_name.exclude).Count -ne 0) {
        Refuse "RULESET_REMOTE_SCOPE_MISMATCH"
    }
    $ExpectedRules = @($Expected.rules)
    $ActualRules = @($Actual.rules)
    if ($ExpectedRules.Count -ne $ActualRules.Count) {
        Refuse "RULESET_REMOTE_RULES_MISMATCH"
    }
    foreach ($Item in $ExpectedRules) {
        $Matches = @($ActualRules | Where-Object { $_.type -ceq $Item.type })
        if ($Matches.Count -ne 1) {
            Refuse "RULESET_REMOTE_RULES_MISMATCH"
        }
        $Observed = $Matches[0]
        if ($Item.type -eq "pull_request") {
            foreach ($Name in @(
                "required_approving_review_count", "require_last_push_approval",
                "required_review_thread_resolution", "dismiss_stale_reviews_on_push",
                "require_code_owner_review"
            )) {
                if ($Observed.parameters.$Name -cne $Item.parameters.$Name) {
                    Refuse "RULESET_REMOTE_REVIEW_MISMATCH"
                }
            }
            $ExpectedMethods = @($Item.parameters.allowed_merge_methods)
            $ActualMethods = @($Observed.parameters.allowed_merge_methods)
            if ($ExpectedMethods.Count -ne $ActualMethods.Count) {
                Refuse "RULESET_REMOTE_REVIEW_MISMATCH"
            }
            foreach ($Method in $ExpectedMethods) {
                if ($ActualMethods -cnotcontains $Method) {
                    Refuse "RULESET_REMOTE_REVIEW_MISMATCH"
                }
            }
        } elseif ($Item.type -eq "required_status_checks") {
            if ($Observed.parameters.strict_required_status_checks_policy -cne
                $Item.parameters.strict_required_status_checks_policy) {
                Refuse "RULESET_REMOTE_CHECKS_MISMATCH"
            }
            $Required = @($Item.parameters.required_status_checks)
            $Provided = @($Observed.parameters.required_status_checks)
            if ($Required.Count -ne $Provided.Count) {
                Refuse "RULESET_REMOTE_CHECKS_MISMATCH"
            }
            foreach ($Check in $Required) {
                $Matches = @($Provided | Where-Object {
                    $_.context -ceq $Check.context
                })
                if ($Matches.Count -ne 1 -or
                    $Matches[0].integration_id -ne $Check.integration_id) {
                    Refuse "RULESET_REMOTE_CHECKS_MISMATCH"
                }
            }
        }
    }
}

$ExpectedRuleTypes = if ($Mode -eq "bootstrap") {
    @("pull_request", "non_fast_forward", "deletion")
} else {
    @("pull_request", "non_fast_forward", "deletion",
      "required_linear_history", "required_status_checks")
}
$ConfiguredTypes = @($Template.rules | ForEach-Object { $_.type })
if ($ConfiguredTypes.Count -ne $ExpectedRuleTypes.Count) {
    Refuse "RULESET_TEMPLATE_REQUIRED_RULE_MISSING"
}
foreach ($RuleType in $ExpectedRuleTypes) {
    if (@($ConfiguredTypes | Where-Object { $_ -ceq $RuleType }).Count -ne 1) {
        Refuse "RULESET_TEMPLATE_REQUIRED_RULE_MISSING"
    }
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
        $PullRules[0].parameters.require_last_push_approval -ne $false -or
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
    $RequiredChecks = @($StatusRules[0].parameters.required_status_checks)
    if ($RequiredChecks.Count -ne $MustPass.Count) {
        Refuse "STRICT_CONTEXTS_MISMATCH"
    }
    foreach ($Context in $MustPass) {
        $Matches = @($RequiredChecks | Where-Object {
            $_.context -ceq $Context
        })
        if ($Matches.Count -ne 1 -or
            $Matches[0].integration_id -ne $TrustedChecksAppId) {
            Refuse "STRICT_CHECK_SOURCE_INVALID"
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
    $Created = @(GhJson "repos/$Repo/rulesets?includes_parents=true" |
        Where-Object { $_.name -eq $Template.name })
    if ($Created.Count -ne 1 -or
        [string]$Created[0].id -notmatch "^[0-9]+$") {
        Refuse "BOOTSTRAP_READBACK_MISSING"
    }
    $Active = GhJson "repos/$Repo/rulesets/$($Created[0].id)"
    ConfirmRulesetMatches $Template $Active
    $Branch = GhJson "repos/$Repo/branches/main"
    if (-not $Branch.protected) {
        Refuse "PROTECTION_NOT_CONFIRMED"
    }
    Write-Output "BOOTSTRAP_ACTIVE: matched live rules and GitHub reports protected main."
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
$BootstrapPolicy = Get-Content -LiteralPath (Join-Path $Folder "main-bootstrap.ruleset.json") -Raw -Encoding UTF8 |
    ConvertFrom-Json -Depth 64
ConfirmRulesetMatches $BootstrapPolicy $BootstrapDetails
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
foreach ($Context in $MustPass) {
    $Matched = @($Checks.check_runs | Where-Object {
        $_.name -ceq $Context -and
        $_.status -eq "completed" -and
        $_.conclusion -eq "success" -and
        $_.app.id -eq $TrustedChecksAppId
    })
    if ($Matched.Count -lt 1) {
        Refuse "REQUIRED_MAIN_HEAD_CHECK_MISSING_OR_UNTRUSTED"
    }
}

# The only allowed update is replacement of our known bootstrap ruleset ID.
# No force push, branch update, manual review spoofing or broad API writes.
& gh api -X PUT "repos/$Repo/rulesets/$RulesetId" --input $TemplatePath 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Refuse "STRICT_RULESET_WRITE_FAILED"
}
$Actual = GhJson "repos/$Repo/rulesets/$RulesetId"
if ($Actual.name -ne $Template.name) {
    Refuse "STRICT_RULESET_NOT_CONFIRMED"
}
ConfirmRulesetMatches $Template $Actual
$FinalBranch = GhJson "repos/$Repo/branches/main"
if (-not $FinalBranch.protected -or
    $FinalBranch.commit.sha -cne $HeadSha) {
    Refuse "MAIN_HEAD_CHANGED_OR_PROTECTION_LOST"
}
Write-Output "STRICT_ACTIVE: matched live rules on unchanged protected main."
