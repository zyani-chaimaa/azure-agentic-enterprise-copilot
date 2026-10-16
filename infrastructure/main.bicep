// Use the same Azure region as our existing resource group.
param location string = resourceGroup().location
// Name of the Azure Container Registry.
param acrName string = 'acrenterprisecopilotdev'

// Create a registry to store our application's Docker images.
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}
// Name of the environment that will host our Container Apps.
param containerAppsEnvironmentName string = 'cae-enterprise-copilot-dev'

// Create a managed environment for running containerized applications.
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    // Use the Consumption workload profile to support usage-based billing.
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// Name of our FastAPI application in Azure.
param containerAppName string = 'ca-enterprise-copilot-dev'

// Create the Container App that runs our FastAPI backend.
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location

  // Give the application its own Microsoft Entra identity.
  identity: {
    type: 'SystemAssigned'
  }

  properties: {
    // Place the application inside our managed environment.
    managedEnvironmentId: containerAppsEnvironment.id
configuration: {
  // Authenticate to Azure Container Registry using Managed Identity.
  registries: [
    {
      server: '${registry.name}.azurecr.io'
      identity: 'system'
    }
  ]

  // Keep the application private during initial deployment.
  ingress: {
    external: false
    targetPort: 8000
    transport: 'auto'
  }
}

    template: {
      containers: [
        {
          name: 'enterprise-copilot-api'

          
          // Use our verified Linux AMD64 Docker image.
          image: '${registry.properties.loginServer}/enterprise-copilot-api:v2'

          // Configure the Microsoft Foundry model used by FastAPI.
          env: [
            {
              // URL of our Microsoft Foundry inference endpoint.
              name: 'AZURE_OPENAI_ENDPOINT'
              value: 'https://enterprise-copilot-dev-resource.services.ai.azure.com/openai/v1/'
            }
            {
              // Name of the deployed GPT model.
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: 'gpt-5.4-mini'
            }
          ]

          // Allocate compute resources to the API container.
          resources: {
            cpu: any('0.5')
            memory: '1Gi'
          }
        }
      ]

      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}
// Reference our existing Microsoft Foundry resource.
// "existing" means Bicep will not create or replace it.
resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: 'enterprise-copilot-dev-resource'
}
// Built-in Azure role: Cognitive Services OpenAI User.
var openAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// Grant our Container App permission to use the Foundry model.
resource foundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, containerApp.id, openAIUserRoleId)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAIUserRoleId)
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
// Built-in Azure role that allows pulling container images.
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

// Allow our Container App's Managed Identity to pull images from ACR.
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, containerApp.id, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}