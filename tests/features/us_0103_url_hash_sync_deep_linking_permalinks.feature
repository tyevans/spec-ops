Feature: Reactive URL Hash State Synchronization, Deep Linking, and Canvas Focus Permalinks

  Scenario: Deep Linking to Specific View Tab and Entity Drawer on Load
    Given the visualizer URL contains a compound state hash:
      | URL Hash                     | Expected Tab | Expected Entity | Drawer Open |
      | #tab=kanban&entity=TASK-0001 | kanban       | TASK-0001       | true        |
      | #tab=adrs&entity=ADR-0001    | adrs         | ADR-0001        | true        |
    When the user accesses the URL in a browser
    Then the visualizer activates the specified tab on initial render
    And the detail slide-over drawer opens automatically populated with the entity's markdown and metadata
    And the underlying dashboard or canvas view renders behind the drawer without layout distortion.

  Scenario: Bidirectional Synchronization of Filter State into URL Hash
    Given the user is on the "kanban" tab
    When the user enters query "preflight", selects status "Refined", and checks "Hide Done"
    Then the browser URL hash updates reactively to:
      """
      #tab=kanban&q=preflight&status=Refined&hideDone=true
      """
    And copying and opening that exact URL in a new browser tab reproduces the exact filtered Kanban state.

  Scenario: Browser Back and Forward History Traversal
    Given the user navigated from "graph" to "gantt", applied a search filter, and opened "TASK-0001"
    When the user clicks the browser "Back" button once
    Then the detail drawer closes while preserving the "gantt" tab and active filter
    And when the user clicks "Back" a second time
    Then the visualizer transitions back to the "graph" tab
    And clicking browser "Forward" re-applies each state transition without full page refreshes.

  Scenario: Graph Canvas Camera Focusing on Deep-Linked Node
    Given a user opens a permalink targeting a node on the relationship canvas:
      """
      #tab=graph&entity=TASK-0001
      """
    When the Canvas 2D simulation initializes
    Then the camera viewport smoothly animates and centers onto the target node "TASK-0001"
    And the target node renders with a prominent animated focus ring
    And the entity detail drawer slides open with a "Copy Deep Link" button that copies the permalink.
