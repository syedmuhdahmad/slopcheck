# Records docs/demo.gif. Run via docs/demo/record.sh (needs Docker), not directly.
# VHS reference: https://github.com/charmbracelet/vhs

Output docs/demo.gif
Require slopfence

Set Shell "bash"
Set Theme "Catppuccin Mocha"
Set FontFamily "JetBrains Mono"
Set FontSize 18
Set LineHeight 1.25
Set Width 1500
Set Height 600
Set Padding 26
Set Margin 22
Set MarginFill "#8B5CF6"
Set WindowBar Colorful
Set WindowBarSize 38
Set BorderRadius 12
Set TypingSpeed 45ms
Set CursorBlink false
# Thumbnail and loop start on the results, not an empty prompt.
Set LoopOffset 80%

Hide
# `cat` gets syntax highlighting (the image has no bat); the text is unchanged.
Type `hl="$PWD/docs/demo/highlight.py"; cat() { python3 "$hl" "$@"; }; cd "$(bash docs/demo/make-project.sh)" && export SLOPFENCE_CACHE_DIR="$PWD/.cache" && PS1='\[\e[1;38;5;141m\]acme-billing\[\e[0m\] \[\e[38;5;244m\]$\[\e[0m\] ' && clear`
Enter
Sleep 800ms
Show

Sleep 500ms
Type "# Your AI assistant just wrote a billing service. Looks done?"
Sleep 900ms
Enter
Type "cat src/billing.py"
Sleep 300ms
Enter
Sleep 3.5s

# Start the results on a clean screen so the final frame (and thumbnail) is tidy.
Hide
Type "clear"
Enter
Sleep 200ms
Show

Sleep 300ms
Type "slopfence ."
Sleep 400ms
Enter
Sleep 7s
