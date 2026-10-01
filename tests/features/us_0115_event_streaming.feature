@US-0115 @TASK-0154
Feature: Real-Time Orchestration Event Streaming and WebSocket Telemetry Bridge

  Scenario: Streaming task lifecycle events to connected clients
    Given a running SpecOps event streaming bridge
    When a task transitions from refined to claimed
    Then a TaskClaimed event envelope is published to the stream in under 20 milliseconds
    And connected subscribers receive the serialized event payload

  Scenario: Historical event replay on new subscriber connection
    Given an existing event store containing historical task lifecycle events
    When a new subscriber connects with a replay request
    Then the bridge streams past events in monotonic sequence order
    And transitions to live streaming seamlessly
