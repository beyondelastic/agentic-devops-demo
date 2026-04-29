// Foundry project connection of type "CustomKeys" used as the OpenAPI tool
// auth in the declarative agent. The Foundry runtime reads the configured
// keys (e.g. x-api-key) and injects them as headers on every tool call.
//
// Surfaced as the `clinical_trial_matcher` connection in the Foundry portal.
param accountName string
param projectName string

@description('Connection name as referenced from the agent metadata / sync_agent.py.')
param connectionName string = 'clinical_trial_matcher'

@description('Target advertised on the connection. Foundry tolerates "-" for OpenAPI auth.')
param target string = '-'

@secure()
@description('API key value injected by Foundry as the `x-api-key` header on every tool call.')
param toolsApiKey string

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: account
  name: projectName
}

resource connection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: connectionName
  properties: {
    authType: 'CustomKeys'
    category: 'CustomKeys'
    target: target
    isSharedToAll: false
    metadata: {
      type: 'openapi'
    }
    credentials: {
      keys: {
        'x-api-key': toolsApiKey
      }
    }
  }
}

output connectionName string = connection.name
output connectionId string = connection.id
