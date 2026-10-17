# 2026-10-11: local quake retention and stock-context duration inputs.
# The five stockfps rows replace their gameplay-only versions from spec12.
# stockpair preserves the source load when unpaced and otherwise uses exact
# shipped bits selected by live shadow mode; the duration uses the tick's
# captured stock context, matching the engine's earlier FPS-byte update.
group objects
stockpair 364CB5 (0x364C82,0x364CC7) | quake retention: 7A81E8[(mode-1)] feeds only B663D0; while camera gate476030 is on use the exact shipped pair selected by live shadow mode, preserving the mutable table load when off or mode unknown
stockpair 37001C (0x36FFDF,0x37002F) | quake retention B663D0: normalize this local copy to the exact shipped live-context pair while camera gate476030 is active; leave the shared mode table and its other consumers untouched
stockpair 3703F5 (0x3703B8,0x370408) | quake retention B663D0: normalize this local copy to the exact shipped live-context pair while camera gate476030 is active
stockpair 3C1E03 (0x3C1DCA,0x3C1E0F) | player quake retention B663D0: restore stock live-context units locally while the objects camera gate476030 is active, independent of player movement and mode-table switches
stockpair 3C5FE1 (0x3C5FA6,0x3C5FEF) | player quake retention B663D0: restore stock live-context units locally while the objects camera gate476030 is active
stockfps 364CBE ("quake",0x364C96,0x364CD8) | quake duration B663D8 is floor(fps/30)*15; while camera gate476030 is active use captured stock-context fps30 in gameplay or60 in stock60 screens, retaining the original byte when off
stockfps 370026 ("quake",0x370021,0x370040) | quake duration B663D8: normalize the fps input to the camera gate's captured stock30/60 context; the tick snapshot matches the engine's FPS-byte sampling order
stockfps 3703FF ("quake",0x3703FA,0x37041B) | quake duration B663D8: normalize the fps input to the camera gate's captured stock30/60 context
stockfps 3C1DE8 ("quake",0x3C1E08,0x3C1E3C) | player quake duration B663D8: use the objects camera gate's captured stock30/60 context, preserving the original byte when that family is off
stockfps 3C5FE6 ("quake",0x3C5FBD,0x3C6008) | player quake duration B663D8: use the objects camera gate's captured stock30/60 context, preserving the original byte when that family is off
