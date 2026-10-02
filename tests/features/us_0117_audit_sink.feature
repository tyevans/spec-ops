@US-0117 @TASK-0160
Feature: Distributed Event Bus and Structured Audit Sink Exporter

  Scenario: Exporting decider events to structured JSONL audit sink
    Given an event store with recorded lifecycle transitions
    When the developer runs spec-ops audit sink with JSONL format
    Then all events are exported into structured lines with sequence numbers and timestamps
    And the command terminates with exit code 0

  Scenario: Filtering exported events by category
    Given an event store containing worker, security, and backlog events
    When the developer exports events filtered to security events
    Then only matching security audit events are emitted to the output file
