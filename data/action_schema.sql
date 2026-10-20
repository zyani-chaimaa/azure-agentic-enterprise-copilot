-- Store proposed business actions and their approval status.
CREATE TABLE dbo.copilot_action_requests (

    -- Unique identifier for each action request.
    action_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT PK_copilot_action_requests
        PRIMARY KEY DEFAULT NEWID(),

    -- Type of action the copilot proposes.
    action_type NVARCHAR(100) NOT NULL,

    -- Target business record, such as an order ID.
    target_id NVARCHAR(100) NOT NULL,

    -- Explanation of why the action was proposed.
    reason NVARCHAR(2000) NOT NULL,

    -- Workflow status; new requests always start as pending.
    status NVARCHAR(20) NOT NULL
        CONSTRAINT DF_action_status DEFAULT 'pending',

    -- Identity that proposed the action.
    proposed_by NVARCHAR(255) NOT NULL,

    -- Identity that approved or rejected the action.
    reviewed_by NVARCHAR(255) NULL,

    -- Time when the action was proposed.
    created_at DATETIME2 NOT NULL
        CONSTRAINT DF_action_created DEFAULT SYSUTCDATETIME(),

    -- Time when a decision was recorded.
    reviewed_at DATETIME2 NULL,

    -- Restrict status values to supported workflow states.
    CONSTRAINT CK_action_status CHECK (
        status IN ('pending', 'approved', 'rejected', 'executed', 'failed')
    ),

    -- Initially allow only the safe manual-review action.
    CONSTRAINT CK_action_type CHECK (
        action_type IN ('flag_order_for_review')
    )
);


-- Record workflow events separately from the current action state.
CREATE TABLE dbo.copilot_action_audit (

    -- Unique identifier for each audit event.
    audit_id BIGINT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_copilot_action_audit PRIMARY KEY,

    -- Link the event to its action request.
    action_id UNIQUEIDENTIFIER NOT NULL,

    -- Event type, such as proposed, approved, or rejected.
    event_type NVARCHAR(50) NOT NULL,

    -- Identity responsible for the event.
    actor NVARCHAR(255) NOT NULL,

    -- Optional details about the event.
    details NVARCHAR(2000) NULL,

    -- UTC timestamp of the event.
    occurred_at DATETIME2 NOT NULL
        CONSTRAINT DF_audit_created DEFAULT SYSUTCDATETIME(),

    -- Enforce a valid parent action request.
    CONSTRAINT FK_audit_action
        FOREIGN KEY (action_id)
        REFERENCES dbo.copilot_action_requests(action_id)
);