-- Store orders flagged for manual review after an approved action.
CREATE TABLE dbo.copilot_order_reviews (

    -- Unique identifier for each review record.
    review_id UNIQUEIDENTIFIER NOT NULL
        CONSTRAINT PK_copilot_order_reviews
        PRIMARY KEY DEFAULT NEWID(),

    -- Link the review to the approved action that created it.
    action_id UNIQUEIDENTIFIER NOT NULL,

    -- Order selected for manual review.
    order_id NVARCHAR(100) NOT NULL,

    -- Explanation provided when the action was proposed.
    reason NVARCHAR(2000) NOT NULL,

    -- Current review status.
    review_status NVARCHAR(30) NOT NULL
        CONSTRAINT DF_order_review_status DEFAULT 'open',

    -- UTC time when the review record was created.
    created_at DATETIME2 NOT NULL
        CONSTRAINT DF_order_review_created DEFAULT SYSUTCDATETIME(),

    -- Prevent the same approved action from creating two reviews.
    CONSTRAINT UQ_order_review_action UNIQUE (action_id),

    -- Ensure the source action exists.
    CONSTRAINT FK_order_review_action
        FOREIGN KEY (action_id)
        REFERENCES dbo.copilot_action_requests(action_id),

    -- Restrict review statuses to supported values.
    CONSTRAINT CK_order_review_status CHECK (
        review_status IN ('open', 'in_progress', 'closed')
    )
);