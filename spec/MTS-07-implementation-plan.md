# MTS-07: Implementation Plan
## Mazyr Technical Specification -- Implementation Roadmap

**Version:** 1.0
**Start Date:** 2026-06-06
**Target MVP:** 2026-06-20 (2 weeks)
**Target v0.5:** 2026-07-06 (1 month)

---

## 1. Philosophy

This plan follows **Law V: Discipline Before Intelligence.**

- One module per day
- Tests before implementation (TDD)
- Git commit after each module
- No skipping steps

---

## 2. Phase 1: Foundation (Week 1) -- "Seed"

**Goal:** Mazyr can boot, has identity, can chat in terminal, memory persists.

### Day 1 -- Project Scaffold
| Task | Output | Time |
|---|---|---|
| Create repo structure | `src/mazyr/{domain,app,infra,interfaces}/` | 1h |
| Setup pyproject.toml | Dependencies, entry points | 1h |
| Setup pytest | `tests/`, `conftest.py`, fixtures | 1h |
| Git init + first commit | `git log` shows scaffold | 30m |

**Deliverable:** `pytest` runs with 0 tests, 0 failures.

### Day 2 -- Domain Layer: Identity
| Task | Output | Time |
|---|---|---|
| Implement `domain/identity.py` | `Identity`, `Mission` dataclasses | 2h |
| Write tests | `tests/domain/test_identity.py` -- 6+ tests | 1h |
| Run tests | All pass | 30m |
| Commit | `feat: identity domain` | 15m |

**Prompt untuk Kimi Code:**
```
Reference: docs/technical-spec/MTS-01-domain-layer.md Section 2
Implement src/mazyr/domain/identity.py with Identity and Mission frozen dataclasses.
Include validation in __post_init__.
Write tests in tests/domain/test_identity.py.
Pure Python, zero external dependencies.
```

### Day 3 -- Domain Layer: Constitution + Filter
| Task | Output | Time |
|---|---|---|
| Implement `domain/constitution.py` | `Law`, `Constitution`, `ValidationResult` | 2h |
| Implement `domain/filter.py` | `FilterAction`, `FilterRule`, `IntegrityFilter` | 2h |
| Write tests | `test_constitution.py`, `test_filter.py` | 1h |
| Commit | `feat: constitution and filter domain` | 15m |

### Day 4 -- Domain Layer: Message + Memory + Skill
| Task | Output | Time |
|---|---|---|
| Implement `domain/message.py` | `Message`, `Conversation` | 1h |
| Implement `domain/memory_entry.py` | `MemoryEntry`, `MemoryQuery`, `MemoryType` | 1h |
| Implement `domain/skills.py` | `Skill`, `SkillEvolution` | 1h |
| Write tests | 3 test files | 1h |
| Commit | `feat: message, memory, skill domains` | 15m |

### Day 5 -- Infrastructure: Config Loader
| Task | Output | Time |
|---|---|---|
| Implement `infra/config_loader.py` | Load YAML frontmatter from `.mazyr/` | 2h |
| Create templates | `templates/identity.md.template` | 1h |
| Write tests | `tests/infra/test_config_loader.py` | 1h |
| Commit | `feat: config loader` | 15m |

### Day 6 -- Application: Bootstrap
| Task | Output | Time |
|---|---|---|
| Implement `app/bootstrap.py` | Boot sequence with validation | 2h |
| Write tests | `tests/app/test_bootstrap.py` | 1h |
| Commit | `feat: bootstrap application` | 15m |

### Day 7 -- Integration + CLI Shell
| Task | Output | Time |
|---|---|---|
| Implement `interfaces/cli.py` skeleton | `mazyr-init`, `mazyr-status` commands | 2h |
| Test init -> status flow | Terminal test | 1h |
| Commit | `feat: cli skeleton` | 15m |

**Week 1 Deliverable:**
```bash
$ mazyr-init
$ mazyr-status
# Shows: Instance: [name], Creator: [name], Status: Configured
```

---

## 3. Phase 2: Core Runtime (Week 2) -- "Sprout"

**Goal:** Mazyr can chat, filter works, memory stores conversations.

### Day 8 -- Infrastructure: SQLite Memory
| Task | Output | Time |
|---|---|---|
| Implement `infra/memory_sqlite.py` | Episodic memory adapter | 2h |
| Setup SQLite schema | Conversations + messages tables | 1h |
| Write tests | `tests/infra/test_memory_sqlite.py` | 1h |
| Commit | `feat: sqlite memory adapter` | 15m |

### Day 9 -- Application: Chat Use Case
| Task | Output | Time |
|---|---|---|
| Implement `app/chat.py` | Receive -> filter -> infer -> filter -> reply | 3h |
| Write tests | `tests/app/test_chat.py` | 1h |
| Commit | `feat: chat use case` | 15m |

### Day 10 -- Infrastructure: Local LLM
| Task | Output | Time |
|---|---|---|
| Implement `infra/llm_local.py` | llama-cli wrapper | 2h |
| Test with Gemma 4 Q4 | Verify output | 1h |
| Commit | `feat: local llm adapter` | 15m |

### Day 11 -- Infrastructure: LLM Router
| Task | Output | Time |
|---|---|---|
| Implement `infra/llm_router.py` | Local vs cloud routing | 1h |
| Implement `infra/llm_cloud.py` | Kimi API wrapper | 1h |
| Write tests | Router tests | 1h |
| Commit | `feat: llm router` | 15m |

### Day 12 -- CLI: Interactive Chat
| Task | Output | Time |
|---|---|---|
| Implement `mazyr-chat` command | Interactive terminal chat | 2h |
| Test full flow | Init -> boot -> chat -> exit | 1h |
| Commit | `feat: interactive chat` | 15m |

### Day 13 -- Application: Audit
| Task | Output | Time |
|---|---|---|
| Implement `app/audit.py` | Health check, drift detection | 2h |
| Implement `mazyr-status` full | Show health metrics | 1h |
| Commit | `feat: audit and status` | 15m |

### Day 14 -- Polish + Bug Fix
| Task | Output | Time |
|---|---|---|
| Fix bugs from Week 1-2 | Stable chat experience | 3h |
| Write integration tests | `tests/e2e/test_boot_chat.py` | 2h |
| Commit | `fix: week 2 polish` | 15m |

**Week 2 Deliverable (MVP):**
```bash
$ mazyr-init
$ mazyr-boot
$ mazyr-chat
You: halo
Aria: [response]
You: exit
$ mazyr-status
# Shows: Filter: Clean, Patterns: Self-Correcting, Runtime: Active
```

---

## 4. Phase 3: Persistence (Week 3) -- "Root"

**Goal:** Memory survives reboot, Qdrant integration, skills evolve.

| Day | Task | Output |
|---|---|---|
| 15 | Qdrant setup + adapter | `infra/memory_qdrant.py` |
| 16 | Semantic memory integration | Facts/preferences storage |
| 17 | Skill system | `app/learn.py`, skill evolution |
| 18 | Memory sync | `app/sync.py`, GitHub snapshot |
| 19 | Systemd service | 24/7 daemon |
| 20 | Graceful shutdown | `mazyr-stop`, cleanup |
| 21 | Week 3 polish | Bug fixes, tests |

**Deliverable:** Aria survives reboot, remembers past conversations, skills update.

---

## 5. Phase 4: Communication (Week 4) -- "Branch"

**Goal:** Aria accessible via WhatsApp/Telegram, cloud relay.

| Day | Task | Output |
|---|---|---|
| 22 | WhatsApp Web adapter | `infra/messenger_whatsapp.py` |
| 23 | Telegram bot adapter | `infra/messenger_telegram.py` |
| 24 | FastAPI webhook server | `interfaces/whatsapp_webhook.py` |
| 25 | Cloud relay client | `interfaces/relay_client.py` |
| 26 | Message routing | Platform-agnostic message handling |
| 27 | Multi-platform test | WhatsApp + Telegram + CLI |
| 28 | Week 4 polish | Bug fixes, documentation |

**Deliverable:** Chat Aria from phone via WhatsApp/Telegram.

---

## 6. Phase 5: Scale (Month 2) -- "Canopy"

**Goal:** Skills mature, self-improvement, economic layer.

| Week | Focus | Deliverable |
|---|---|---|
| 5 | Skills | Voidlight Vision, Aetherflow, MetraNet skills |
| 6 | Learning | Pattern extraction, skill evolution log |
| 7 | Economic | Agentic wallet, x402 protocol, self-funding |
| 8 | Community | Clone protocol, documentation, first external instance |

---

## 7. Daily Ritual

```bash
# Morning (15 min)
git pull
pytest tests/domain -q  # Fast feedback

# Work (2-3 hours)
# Implement 1 module
# Write tests
# pytest
# git commit

# Evening (15 min)
git push
update evolution.log
```

---

## 8. Risk Mitigation

| Risk | Probability | Mitigation |
|---|---|---|
| Local LLM too slow | High | Fallback to cloud, optimize ngl |
| Memory grows too large | Medium | Auto-prune, compression |
| WhatsApp Web breaks | Medium | Telegram as primary, WhatsApp backup |
| Burnout | High | Strict 1 module/day, weekend rest |
| Kimi Code drift | Medium | Reference MTS docs, review output |

---

## 9. Success Criteria

### MVP (Week 2)
- [ ] `mazyr-init` creates instance
- [ ] `mazyr-boot` starts daemon
- [ ] `mazyr-chat` interactive chat
- [ ] Filter blocks bad messages
- [ ] Memory persists across sessions
- [ ] `mazyr-status` shows health

### v0.5 (Month 1)
- [ ] 24/7 systemd daemon
- [ ] WhatsApp/Telegram access
- [ ] Qdrant semantic memory
- [ ] Skill system
- [ ] GitHub sync
- [ ] 80%+ test coverage

### v1.0 (Month 2)
- [ ] Clone protocol works
- [ ] External user deploys instance
- [ ] Economic layer (optional)
- [ ] Full documentation
- [ ] Species declared "stable"
