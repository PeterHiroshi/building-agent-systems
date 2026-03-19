# Contributing to Building Agent Systems

Thanks for your interest in contributing. This project aims to be the most practical, beginner-friendly guide to building AI agent systems.

## How to Contribute

### Reporting Issues

- Use the issue tracker for bugs, unclear documentation, or missing content
- Include specific details: what section, what's confusing, what you expected

### Adding Content

The most valuable contributions are:

1. **Real-world case studies** — Share how you applied a pattern in production. What worked, what didn't, and what you learned.

2. **New examples** — Complete, runnable agent implementations. Follow the existing example structure:
   ```
   examples/your-example/
     README.md    # Pattern used, difficulty, key concepts
     agent.py     # Runnable code with mock tools
   ```

3. **Reference improvements** — Deeper coverage of a topic, better explanations, additional code in other languages.

4. **Translations** — Help make this accessible to non-English speakers.

### Writing Style

- **Practical over theoretical** — Every section should have runnable code or a concrete example
- **Beginner-friendly but not shallow** — Explain the "why" behind decisions, not just the "what"
- **Direct and concise** — Say it once, clearly. Avoid filler words and unnecessary preamble
- **Opinionated** — Take a position. "Use X when Y" is better than "You could use X or Z"

### Code Examples

- Use the Anthropic SDK (Python preferred, TypeScript and Go welcome)
- Include mock tool implementations so examples run without external dependencies
- Use the latest model IDs (check README for current recommendations)
- Add comments only where the logic isn't self-evident

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b add-new-example`)
3. Make your changes
4. Test that code examples run (or at least parse) correctly
5. Submit a PR with a clear description of what you added and why

### What We're NOT Looking For

- Pure theory without practical application
- Vendor-specific integrations (keep it focused on Anthropic/Claude)
- Content that duplicates existing sections
- Changes to SKILL.md that would make it significantly larger (it needs to stay focused for skill loading)

## Structure

```
SKILL.md                    # Core skill (loaded by Claude Code)
README.md                   # Project landing page
references/                 # Deep-dive reference guides
  patterns-reference.md     # Workflow patterns
  tool-design-reference.md  # Tool design principles
  context-engineering-reference.md
  think-tool-reference.md
  evals-reference.md
  rag-reference.md
examples/                   # Complete, runnable examples
  research-agent/
  support-router/
  code-review-agent/
  multi-agent-researcher/
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
