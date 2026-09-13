# Installation workflow for the assistant

Use this workflow when the user says “Installe cet agent :
https://github.com/ncleton/leadgenerator” or asks to install this source folder.
Do the installation, not merely present commands for the user to run. Keep
progress messages concise and use the conversation's language.

## Choose the source folder and host

1. If the user already opened a source checkout, use it without moving their
   files. Otherwise choose an unused durable parent folder, then place this
   repository in its `code/` child. Prefer `git clone` from the official repository.
   If Git is unavailable, download the official GitHub source ZIP and extract its
   contents into `code/`; do not ask the user to install Git just to get started.
   Never overwrite an existing directory or use the plugin cache as a workspace.
2. Infer the host from this conversation: Codex uses `codex`; Claude Desktop,
   including its graphical Code tab, uses `claude-desktop`; terminal Claude Code
   uses `claude-code`. Do not ask the user to choose an internal package format.
   If the host genuinely cannot be determined, ask one short question.
3. Read this repository's `AGENTS.md` and run its installer from the source root:

   | Platform | Installer |
   | --- | --- |
   | macOS / Linux | `./scripts/install_client.sh --host <host>` |
   | Windows | `.\scripts\install_client.cmd -HostTarget <host>` |

   The default host is Codex. The installers prepare dependencies, Chromium,
   private storage and the selected host's MCP registration. Handle normal local
   setup yourself, but respect host permission prompts and let the user complete
   authentication. Never bypass approvals or request credentials in chat.

Do not call `codex plugin add` directly, hand-copy the plugin cache, import
browser cookies, or install a different lead-generation product. The installer
performs the runtime preparation and private-folder binding as one workflow.

## Check the installation and hand off

The source checkout normally lives in `<parent>/code`; private business data
lives in `<parent>/donnees-privees`, outside Git. Other checkout names use a
sibling `<checkout-name>-donnees-privees`. Report the actual path returned by the
installer, not a guessed home directory. A fresh private folder contains no
objectives. If it already contains data, disclose that fact; do not delete or
import anything automatically.

Installing from another source folder changes the one active Codex plugin
binding, or rebinds a recognized Lead Generator Claude registration. Other
connectors and customized instructions must remain intact. An unrecognized
connector conflict requires review, not a blind overwrite.

Only report success after the installer and its available checks complete.
Ask the user to **quit and restart Codex or Claude completely**. When the
conversation resumes, discover the newly loaded tools, call
`get_lead_interface_mode`, then resolve the initial prospecting objective. Do not
ask the user to repeat installation commands or choose technical settings.
Claude Code must reopen the same local project. Hosts do not start an assistant
turn merely because the application restarted: explain this only if needed,
rather than claiming that a background onboarding conversation has run.

On a fresh store, the first lead workflow must ask for the user's offer and
target. Never seed a commercial example as a real objective. Successful MCP
validation does not by itself prove that the user has seen the interface.

For a folder copied to another computer, use the same installer from its new
source path. See [storage.md](storage.md): close the apps before copying, retain
both code and private data, reconnect credentials and browsers, and reconfigure
host-owned schedules. Never publish or share the private parent archive.
