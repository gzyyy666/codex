@{
    # This is a default-deny source mirror policy. Paths not allowed here are
    # reported as skipped by the preview tool and are never copied by default.
    RootFiles = @(
        'CHANGELOG.md',
        'DESIGN.md',
        'FITNESS_LEDGER_MAINTENANCE.md',
        'FUNCTIONAL_REVIEW_BRIEF.md',
        'FUNCTION_INDEX.md',
        'PRODUCT.md',
        'PROJECT_BOOTSTRAP.md',
        'PROJECT_CONTEXT.md',
        'PROJECT_INDEX.md',
        'README.md',
        'REGRESSION_CHECKLIST.md',
        'ledger_commands.py',
        'stable_app.pyw',
        'start_mobile_viewer.py'
    )

    DirectoryRules = @{
        'assets' = @('.png', '.ico', '.webp', '.svg')
        'cloud_sync' = @('.py', '.md', '.example.json', 'cloud_config.local.json.example')
        'docs' = @('.md')
        'fitness_ledger_core' = @('.py')
        'mini_program' = @('.js', '.json', '.wxml', '.wxss', '.md', '.webp', '.png', '.jpg', '.jpeg')
        'mobile_viewer' = @('.py', '.html', '.css', '.js', '.md')
        'tools' = @('.py', '.mjs', '.md')
        'web_desktop' = @('.py', '.pyw', '.js', '.css', '.html', '.md', '.json', '.png', '.ico', '.webp', '.svg', '.ttf')
    }

    ExplicitExclusions = @(
        'data/', 'backups/', 'logs/', 'work/',
        'cloud_sync/out/',
        'cloud_sync/cloud_sync_config.json',
        'cloud_sync/cloud_config.local.json',
        'mini_program/project.private.config.json',
        'mini_program/miniprogram/config/env.local.js',
        'web_desktop/.edge-profile/', 'web_desktop/.qa-edge'
    )

    LargeFileBytes = 5242880
}
