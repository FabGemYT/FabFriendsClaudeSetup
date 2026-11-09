# Credits and licences

Most of this setup is the owner's own work. The skills below come from other
people's open-source projects and keep their original licences; thank them.
Folders marked *modified* were changed here so they run reliably; the change is
named, as the Apache-2.0 licence asks.

| Skill | Source | Licence | Changes here |
|---|---|---|---|
| accessibility | addyosmani/web-quality-skills | MIT |  |
| agent-browser | vercel-labs/agent-browser | Apache-2.0 |  |
| ai-sdk | vercel/ai (skills/use-ai-sdk) | Apache-2.0 | modified: description rewritten to be directive |
| ai-seo | coreyhaines31/marketingskills | MIT |  |
| aso | coreyhaines31/marketingskills | MIT |  |
| best-practices | addyosmani/web-quality-skills | MIT |  |
| blogs | original to this setup | this setup's own |  |
| claude-ads | AgriciDaniel/claude-ads | MIT |  |
| commit-push-pr | original to this setup | this setup's own |  |
| core-web-vitals | addyosmani/web-quality-skills | MIT |  |
| deploy-to-vercel | vercel-labs/agent-skills | MIT | modified: never deploys to production |
| frontend-design-official | anthropics/skills | Apache-2.0 | modified: locally edited |
| harness-review | original to this setup | this setup's own |  |
| health | original to this setup | this setup's own |  |
| homepage | original to this setup | this setup's own |  |
| hyperframes | heygen-com/hyperframes | Apache-2.0 |  |
| hyperframes-animation | heygen-com/hyperframes | Apache-2.0 |  |
| hyperframes-cli | heygen-com/hyperframes | Apache-2.0 |  |
| hyperframes-core | heygen-com/hyperframes | Apache-2.0 |  |
| hyperframes-creative | heygen-com/hyperframes | Apache-2.0 |  |
| hyperframes-keyframes | heygen-com/hyperframes | Apache-2.0 |  |
| hyperframes-media | heygen-com/hyperframes | Apache-2.0 |  |
| hyperframes-registry | heygen-com/hyperframes | Apache-2.0 |  |
| impeccable | pbakaus/impeccable | Apache-2.0 | modified: 69 template placeholders filled in so it runs |
| kickoff | original to this setup | this setup's own |  |
| lp-conversion-audit | autonnel/autonnel-skills (landing-page-conversion-audit) | Apache-2.0 |  |
| media-use | heygen-com/hyperframes | Apache-2.0 | modified: <SKILL_DIR> defined once; two broken relative links fixed |
| mk-ad-creative | coreyhaines31/marketingskills (ad-creative) | MIT |  |
| mk-ads | coreyhaines31/marketingskills (ads) | MIT |  |
| mk-copywriting | coreyhaines31/marketingskills (copywriting) | MIT |  |
| mk-cro | coreyhaines31/marketingskills (cro) | MIT |  |
| mk-lead-magnets | coreyhaines31/marketingskills (lead-magnets) | MIT |  |
| mk-marketing-psychology | coreyhaines31/marketingskills (marketing-psychology) | MIT |  |
| mk-offers | coreyhaines31/marketingskills (offers) | MIT |  |
| performance | addyosmani/web-quality-skills | MIT |  |
| plan-first | original to this setup | this setup's own |  |
| playwright-cli | microsoft/playwright-cli | Apache-2.0 |  |
| programmatic-seo | coreyhaines31/marketingskills | MIT |  |
| react-native-best-practices | vercel-labs/agent-skills (react-native-skills) | MIT |  |
| schema | coreyhaines31/marketingskills | MIT |  |
| seo | AgriciDaniel/claude-seo | MIT |  |
| seo-aeo-best-practices | sanity-io/agent-toolkit | MIT |  |
| seo-audit | AgriciDaniel/claude-seo | MIT |  |
| seo-backlinks | AgriciDaniel/claude-seo | MIT |  |
| seo-cluster | AgriciDaniel/claude-seo | MIT |  |
| seo-competitor-pages | AgriciDaniel/claude-seo | MIT |  |
| seo-content | AgriciDaniel/claude-seo | MIT |  |
| seo-content-brief | AgriciDaniel/claude-seo | MIT |  |
| seo-dataforseo | AgriciDaniel/claude-seo | MIT |  |
| seo-drift | AgriciDaniel/claude-seo | MIT |  |
| seo-ecommerce | AgriciDaniel/claude-seo | MIT |  |
| seo-flow | AgriciDaniel/claude-seo | MIT |  |
| seo-geo | AgriciDaniel/claude-seo | MIT |  |
| seo-google | AgriciDaniel/claude-seo | MIT |  |
| seo-hreflang | AgriciDaniel/claude-seo | MIT |  |
| seo-image-gen | AgriciDaniel/claude-seo | MIT |  |
| seo-images | AgriciDaniel/claude-seo | MIT |  |
| seo-local | AgriciDaniel/claude-seo | MIT |  |
| seo-maps | AgriciDaniel/claude-seo | MIT |  |
| seo-page | AgriciDaniel/claude-seo | MIT |  |
| seo-plan | AgriciDaniel/claude-seo | MIT |  |
| seo-programmatic | AgriciDaniel/claude-seo | MIT |  |
| seo-schema | AgriciDaniel/claude-seo | MIT |  |
| seo-sitemap | AgriciDaniel/claude-seo | MIT |  |
| seo-sxo | AgriciDaniel/claude-seo | MIT |  |
| seo-technical | AgriciDaniel/claude-seo | MIT |  |
| server-side-tracking | autonnel/autonnel-skills (server-side-conversion-tracking) | Apache-2.0 |  |
| site-architecture | coreyhaines31/marketingskills | MIT |  |
| skill-creator | anthropics/skills | Apache-2.0 |  |
| store-screenshots | FabGemYT/store-screenshots | MIT |  |
| supabase | supabase/agent-skills | MIT |  |
| supabase-postgres-best-practices | supabase/agent-skills | MIT |  |
| ui-ux-pro-max | nextlevelbuilder/ui-ux-pro-max-skill | MIT | modified: script paths made absolute; Windows Python launcher |
| unslop | original to this setup | this setup's own |  |
| vercel-react-best-practices | vercel-labs/agent-skills (react-best-practices) | MIT |  |
| web-design-guidelines | vercel-labs/agent-skills | MIT |  |
| web-quality-audit | addyosmani/web-quality-skills | MIT |  |

## Downloaded at install instead of copied

- **remotion-best-practices** from `remotion-dev/skills`: the source repo publishes no licence, so it is not ours to redistribute. The installer runs `npx -y skills add remotion-dev/skills --skill remotion-best-practices -g -y`.

The rest of this repository (rules, hooks, tools, the installer) is shared by its
owner for friends to use on their own machines.
