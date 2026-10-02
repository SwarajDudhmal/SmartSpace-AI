# SmartSpace AI flowchart and system design

Generated with the built-in image_gen tool using the user's two reference images. The diagrams are concise conceptual overviews of the project, with simple shapes and text.

## Flowchart prompt

Use case: infographic-diagram.
Create one clean, accurate FLOWCHART for the SmartSpace AI interior layout project, using the attached reference only for its simple academic flowchart style. Do not copy chatbot content, slide decorations, screenshot borders, or playback controls. The user prefers simple shapes and text, NO photos, room renderings, or decorative illustrations.

Title: "Flow Chart"
Subtitle: "SmartSpace AI — Interior Layout Planning"
White background, black/dark gray typography and thin orthogonal arrow connectors, very light gray rounded process boxes, standard diamond decision nodes, small filled start circle and double-ring end circle. A restrained navy accent in title is fine. Spacious portrait layout, sharp readable sans-serif lettering, balanced margins, consistent shapes. Use only concise labels below, not paragraphs.

Build exactly this logical flow:
Start circle
down to rounded box "Enter Room Details & Optional Photo"
down to rounded box "Validate Inputs & Prepare Room Data"
down to rounded box "Run Photo Detection When Available"
down to diamond "Furniture Detected?"

Branch LEFT from this diamond labeled "Yes" to rounded box "Build Layout from Detections".
Branch RIGHT from this diamond labeled "No" to rounded box "Load Starter Layout".
Both branches merge cleanly into a single rounded box below:
"Optimize Furniture Layout"
small second line inside same box: "DQN-guided / spatial search"

Then down to rounded box:
"Evaluate Layout"
small second line: "SAT collisions • A* paths • Budget"

Then down to rounded box "Display 2D / 3D Studio"
Then down to diamond "Edit Layout?"
The "Yes" branch runs to a small side process box "Update Furniture", and a clear outer loop arrow runs from that box back to "Evaluate Layout". The loop must enter evaluation, NOT restart photo detection or optimization.
The "No" branch continues downward to rounded box "Save / Export Design"
Then down to double-ring end circle.

Keep flow top-to-bottom. Branch labels must be attached to correct connectors and all arrowheads point correctly. No disconnected boxes, no overlapping lines/text. The two detection branches rejoin only at optimization. This is an overview, so do not add implementation details, databases, model dimensions, files, HTTP, queues, or extra decisions.
Generate exactly ONE finished flowchart image with all content fully visible.

## System design prompt

Use case: infographic-diagram.
Create exactly ONE "System Design" diagram for SmartSpace AI, an interior layout planning application. Use the attached system-design example only for its academic UML-like visual style: user actor at top, nested component boxes, labeled connections, and database below. Do NOT reproduce chatbot terminology, screenshot/slide decorations, cropped edges, or gears. The user wants simple shapes, a stick-figure user, and a database cylinder only: NO photos, furniture pictures, room renderings, or realistic imagery.

Main title: "System Design"
Subtitle: "SmartSpace AI — Interior Layout Planning"
White background; clean black/dark gray thin outlines and arrows; light gray rounded component containers; navy headings; a very subtle pale green service container and pale amber database cylinder allowed. Portrait composition, readable sans-serif text, spacious balanced layout. Keep labels short. No code, files, URLs, model dimensions, framework version numbers, explanations, or paragraphs.

LAYOUT:
1. At the top: small standard stick-figure actor labeled "User".
Below: a medium-wide rounded container titled "Web Interface", containing two side-by-side small boxes:
"Project Setup"
"2D / 3D Studio"
A simple arrow from User to this Web Interface labeled "Enter details / edit design".

2. Beneath Web Interface: one large light-gray rounded outer boundary titled "Application Server".
Inside the upper part of this outer boundary: a smaller wide container titled "Flask Backend", containing two boxes:
"REST API & Sessions"
"Background Jobs"
Arrow between these inner boxes: REST API & Sessions → Background Jobs, labeled "Queue AI work".

Inside the lower part of the SAME Application Server boundary: a wide pale-green container titled "AI & Spatial Services".
Inside, three side-by-side rounded boxes, with ONLY this concise content:
"YOLO Vision"
"Furniture detection"

"Layout Optimizer"
"DQN / spatial search"

"Layout Evaluator"
"SAT • A* • Budget"

Connect YOLO Vision → Layout Optimizer with a short arrow between boxes.
Connect Layout Optimizer ↔ Layout Evaluator with a short bidirectional arrow between boxes.
Connect Background Jobs down to the top of the AI & Spatial Services container with a single arrow labeled "Detect / recommend / optimize".
Connect REST API & Sessions directly to Layout Evaluator with an independent neat line along the RIGHT INSIDE margin of the Application Server, labeled "Evaluate". This direct route bypasses Background Jobs. Reserve enough whitespace for this line.

3. At the very bottom, BELOW the Application Server boundary: one wide pale-amber database cylinder labeled:
"SQLite Database"
"Users • Projects • Furniture • Presets"
Use large enough text to read easily.

EXTERNAL CONNECTIONS:
Web Interface ↔ Flask Backend: a clear bidirectional vertical arrow labeled "Requests / results". This indicates the browser communicates through Flask.
Flask Backend ↔ SQLite Database: one neat outer connector running down the LEFT OUTSIDE margin of Application Server, labeled "Save / load". Connect its top endpoint specifically to the Flask Backend container, not to Web Interface.
AI & Spatial Services ↔ SQLite Database: one vertical connector from service container through bottom of server boundary to database, labeled "Catalog / presets".
No direct line from User or Web Interface to the database.
All connections must have precise endpoints, no crossing boxes, no overlapping labels. Keep the outer Flask-to-database connection visually distinct from the services-to-database connection.
The Application Server contains both Flask Backend and AI & Spatial Services; these are modules in the same application, not separate deployed servers.
Do not add any other components, training pipeline, model-file store, clouds or extra arrows.
Generate a single clean complete diagram, with no inset duplicates and all labels spelled correctly.
