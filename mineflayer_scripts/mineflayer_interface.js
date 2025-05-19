const mineflayer = require('mineflayer');
const mineflayerPathfinder = require('mineflayer-pathfinder');
var Vec3 = require('vec3').Vec3;

let bot = null;
let mcData = null;

async function initializeBot(options) {
  if (bot && bot.username && bot.entity) {
    console.log('Mineflayer Bot already initialized and spawned.');
    return { status: "already_initialized", username: bot.username };
  }

  if (bot) {
    console.log('Cleaning up existing bot instance before re-initialization.');
    try {
      bot.quit('Re-initializing');
    } catch (e) {
      console.warn('Error quitting existing bot instance:', e.message);
    }
    bot = null;
    mcData = null;
  }

  console.log('Creating new Mineflayer bot instance with options:', options);
  bot = mineflayer.createBot(options);
  bot.loadPlugin(mineflayerPathfinder.pathfinder);

  try {
    await new Promise((resolve, reject) => {
      let spawned = false;
      
      const listeners = {
        loginListener: () => {
          try {
            mcData = require('minecraft-data')(bot.version);
            console.log(`Mineflayer Bot logged in. mcData version: ${bot.version}. Username: ${bot.username}`);
          } catch (mcDataError) {
            console.error('Failed to load minecraft-data:', mcDataError);
            if (!spawned) reject(new Error(`Failed to load minecraft-data: ${mcDataError.message}`));
          }
        },
        spawnListener: () => {
          spawned = true;
          console.log(`Mineflayer Bot '${bot.username}' spawned in ADK project.`);
          bot.removeListener('error', listeners.errorListener);
          bot.removeListener('kicked', listeners.kickListener);
          bot.removeListener('login', listeners.loginListener);
          
          bot.on('error', (err) => console.error('Mineflayer Bot Error (post-spawn):', err));
          bot.on('kicked', (reason) => console.log('Mineflayer Bot Kicked (post-spawn):', reason));
          
          resolve();

          // Optional initial teleport
          if (options.initial_teleport_coords &&
              Array.isArray(options.initial_teleport_coords) &&
              options.initial_teleport_coords.length === 3 &&
              options.initial_teleport_coords.every(coord => typeof coord === 'number')) {
            
            const [tpX, tpY, tpZ] = options.initial_teleport_coords;
            console.log(`Teleporting the bot '${bot.username}' to ${tpX} ${tpY} ${tpZ}`);
            bot.chat(`/tp ${bot.username} ${tpX} ${tpY} ${tpZ}`);
          }
        },
        errorListener: (err) => {
          if (!spawned) {
            console.error('Mineflayer Bot Error (pre-spawn):', err);
            bot.removeListener('login', listeners.loginListener);
            bot.removeListener('spawn', listeners.spawnListener);
            bot.removeListener('kicked', listeners.kickListener);
            reject(err);
          }
        },
        kickListener: (reason) => {
          if (!spawned) {
            console.log('Mineflayer Bot Kicked (pre-spawn):', reason);
            bot.removeListener('login', listeners.loginListener);
            bot.removeListener('spawn', listeners.spawnListener);
            bot.removeListener('error', listeners.errorListener);
            reject(new Error(String(reason)));
          }
        }
      };
      
      bot.once('login', listeners.loginListener);
      bot.once('spawn', listeners.spawnListener);
      bot.once('error', listeners.errorListener);
      bot.once('kicked', listeners.kickListener);
    });

    return { status: "success", username: bot.username, message: "Mineflayer bot initialized and spawned." };

  } catch (error) {
    console.error('Failed to initialize Mineflayer bot (outer promise catch):', error);
    if (bot) {
        try { bot.quit('Initialization failed'); } catch (e) { /* ignore */ }
        bot = null;
        mcData = null;
    }
    const errorMessage = error && error.message ? error.message : "Unknown error during initialization.";
    return { status: "error", message: errorMessage };
  }
}

async function goToXYZ(x, y, z, operationId) {
  if (!bot || !bot.pathfinder) {
    return { operationId, status: "error", message: "Bot not initialized or pathfinder not loaded." };
  }
  if (!bot.registry) {
    return { operationId, status: "error", message: "bot.registry not available (mcData not loaded)." };
  }

  console.log(`JS: goToXYZ(${x}, ${y}, ${z}) called with operationId: ${operationId}`);

  const goal = new mineflayerPathfinder.goals.GoalBlock(x, y, z);

  let originalThinkTimeout;
  const overallNavigationTimeoutMs = 120000; // 2 minutes for the whole operation (path calc + travel)
  const pathCalculationTimeoutToSet = 60000; // 60 seconds for A* path calculation

  return new Promise(async (resolve, reject) => {
    const navigationTimeoutId = setTimeout(() => {
      bot.pathfinder.stop();
      console.error(`JS: Overall navigation timeout for operationId ${operationId} (goal ${x},${y},${z}) after ${overallNavigationTimeoutMs / 1000}s`);
      const timeoutErrorResult = { operationId, status: "error", message: `Overall navigation timed out for goal ${x},${y},${z}` };
      if (global.python) global.python.emit('mineflayerTaskComplete', timeoutErrorResult);
      reject(timeoutErrorResult);
    }, overallNavigationTimeoutMs);

    try {
      if (bot.pathfinder.thinkTimeout !== undefined) {
        originalThinkTimeout = bot.pathfinder.thinkTimeout;
        bot.pathfinder.thinkTimeout = pathCalculationTimeoutToSet;
        console.log(`JS: Temporarily set pathfinder.thinkTimeout to ${pathCalculationTimeoutToSet}ms for operationId ${operationId}`);
      }

      await bot.pathfinder.goto(goal);

      clearTimeout(navigationTimeoutId);
      console.log(`JS: Reached goal for operationId ${operationId}: ${x}, ${y}, ${z}`);
      const successResult = { operationId, status: "success", message: `Reached goal: ${x}, ${y}, ${z}` };
      if (global.python) global.python.emit('mineflayerTaskComplete', successResult);
      resolve(successResult);

    } catch (err) {
      clearTimeout(navigationTimeoutId);
      console.error(`JS: pathfinder.goto error for operationId ${operationId} (goal ${x},${y},${z}): ${err.message || String(err)}`);
      const errorResult = { operationId, status: "error", message: `Pathfinding error: ${String(err.message || err)}` };
      if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
      reject(errorResult);

    } finally {
      if (originalThinkTimeout !== undefined) {
        bot.pathfinder.thinkTimeout = originalThinkTimeout;
        console.log(`JS: Restored pathfinder.thinkTimeout to ${originalThinkTimeout}ms for operationId ${operationId}`);
      }
    }
  });
}

function findBlock(blockTypeName, maxDistance = 64, count = 1) {
  if (!bot || !bot.registry) return { status: "error", message: "Bot not initialized or registry not available." };
  const block = bot.findBlock({
    matching: bot.registry.blocksByName[blockTypeName]?.id,
    maxDistance: maxDistance,
    count: count
  });
  if (block) {
    return { status: "success", location: { x: block.position.x, y: block.position.y, z: block.position.z } };
  }
  return { status: "error", message: `${blockTypeName} not found within ${maxDistance} blocks.` };
}

async function mineBlock(blockTypeName, x, y, z, operationId) {
  if (!bot) {
    const errorResult = { operationId, status: "error", message: "Bot not initialized." };
    if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
    return errorResult;
  }
  console.log(`JS: mineBlock(${blockTypeName}, ${x},${y},${z}) called with operationId: ${operationId}`);

  if (bot.targetDigBlock) {
    const busyMessage = `Bot is already digging ${bot.targetDigBlock.name}. Cannot start new dig operation.`;
    console.log(`JS: ${busyMessage} for operationId ${operationId}`);
    const errorResult = { operationId, status: "error", message: busyMessage };
    if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
    return errorResult;
  }

  const targetBlock = bot.blockAt(new Vec3(x, y, z));
  if (!targetBlock) {
    const errorMsg = `No block found at ${x},${y},${z}.`;
    console.log(`JS: ${errorMsg} for operationId ${operationId}`);
    const errorResult = { operationId, status: "error", message: errorMsg };
    if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
    return errorResult;
  }
  
  if (targetBlock.name !== blockTypeName) {
    const errorMsg = `Block at ${x},${y},${z} is ${targetBlock.name}, not ${blockTypeName}.`;
    console.log(`JS: ${errorMsg} for operationId ${operationId}`);
    const errorResult = { operationId, status: "error", message: errorMsg };
    if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
    return errorResult;
  }

  if (!bot.canDigBlock(targetBlock)) {
    const errorMsg = `Cannot dig ${blockTypeName} at ${x},${y},${z}. Might need a better tool or allow break time.`;
    console.log(`JS: ${errorMsg} for operationId ${operationId}`);
    const errorResult = { operationId, status: "error", message: errorMsg };
    if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
    return errorResult;
  }

  (async () => {
    try {
      console.log(`JS: Starting to dig ${targetBlock.name} at ${x},${y},${z} for operationId ${operationId}`);
      await bot.dig(targetBlock);
      console.log(`JS: Successfully mined ${targetBlock.name} at ${x},${y},${z} for operationId ${operationId}`);
      if (global.python) {
        global.python.emit('mineflayerTaskComplete', {
          operationId,
          status: "success",
          collected_item: targetBlock.name,
          message: `Successfully mined ${targetBlock.name}`
        });
      }
    } catch (err) {
      console.error(`JS: Mining failed for ${targetBlock.name} at ${x},${y},${z} for operationId ${operationId}: ${err.message}`);
      console.error(err.stack);
      if (global.python) {
        global.python.emit('mineflayerTaskComplete', {
          operationId,
          status: "error",
          message: `Mining failed: ${err.message}`
        });
      }
    }
  })();

  return { status: "pending", operationId: operationId, message: `Mining of ${blockTypeName} at (${x},${y},${z}) initiated.` };
}

function getInventory() {
    if (!bot || !bot.inventory) return { status: "error", message: "Bot not initialized or inventory not available." };
    const items = bot.inventory.items().map(item => ({ name: item.name, count: item.count, type: item.type }));
    return { status: "success", inventory: items };
}

async function craftItem(itemName, quantity, recipeShape, ingredients, craftingTableNeeded, operationId) {
    if (!bot || !bot.registry) {
        const errorResult = { operationId, status: "error", message: "Bot not initialized or bot.registry not available." };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }
    console.log(`JS: craftItem(${itemName}, ${quantity}) called with operationId: ${operationId}`);

    const item = bot.registry.itemsByName[itemName];
    if (!item) {
        const errorResult = { operationId, status: "error", message: `Unknown item: ${itemName}` };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }

    const craftingTableId = bot.registry.blocksByName.crafting_table ? bot.registry.blocksByName.crafting_table.id : null;
    if (craftingTableNeeded && !craftingTableId) {
        const errorResult = { operationId, status: "error", message: "Crafting table block ID not found in bot.registry." };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }
    
    const craftingTableBlock = craftingTableNeeded ? bot.findBlock({ matching: craftingTableId, maxDistance: 64 }) : null;
    if (craftingTableNeeded && !craftingTableBlock) {
        const errorResult = { operationId, status: "error", message: "Crafting table not found nearby." };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }

    const recipes = bot.recipesFor(item.id, null, 1, craftingTableBlock);
    if (!recipes || recipes.length === 0) {
        const errorMsg = `No recipe found for ${itemName}` + (craftingTableNeeded ? " with a crafting table nearby." : " in inventory.");
        const errorResult = { operationId, status: "error", message: errorMsg };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }
    
    const recipeToUse = recipes;

    bot.craft(recipeToUse, quantity, craftingTableBlock)
        .then(() => {
            console.log(`JS: Successfully crafted ${quantity} of ${itemName} for operationId ${operationId}`);
            if (global.python) {
                global.python.emit('mineflayerTaskComplete', {
                    operationId,
                    status: "success",
                    crafted_item: itemName,
                    quantity_crafted: quantity
                });
            }
        })
        .catch((err) => {
            console.error(`JS: Crafting failed for ${itemName} (operationId ${operationId}): ${err.message}`);
            if (global.python) {
                global.python.emit('mineflayerTaskComplete', {
                    operationId,
                    status: "error",
                    message: `Crafting failed: ${err.message}`
                });
            }
        });
    
    return { status: "pending", operationId: operationId, message: `Crafting of ${quantity} ${itemName}(s) initiated.` };
}

async function placeBlock(itemName, x, y, z, refBlockX, refBlockY, refBlockZ, faceVectorX, faceVectorY, faceVectorZ, operationId) {
    if (!bot || !bot.registry) { 
        const errorResult = { operationId, status: "error", message: "Bot not initialized or bot.registry not available." };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }
    console.log(`JS: placeBlock(${itemName}) at ref (${refBlockX},${refBlockY},${refBlockZ}) face (${faceVectorX},${faceVectorY},${faceVectorZ}) called with operationId: ${operationId}`);

    const itemToPlace = bot.inventory.items().find(item => item.name === itemName);
    if (!itemToPlace) {
        const errorResult = { operationId, status: "error", message: `Item ${itemName} not in inventory.` };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }

    const referenceBlock = bot.blockAt(new Vec3(refBlockX, refBlockY, refBlockZ));
    if (!referenceBlock) {
        const errorResult = { operationId, status: "error", message: "Reference block not found." };
        if (global.python) global.python.emit('mineflayerTaskComplete', errorResult);
        return errorResult;
    }
    const faceVec = new Vec3(faceVectorX, faceVectorY, faceVectorZ);

    bot.equip(itemToPlace, 'hand')
      .then(() => bot.placeBlock(referenceBlock, faceVec))
      .then(() => {
        const placedLocation = {x: refBlockX + faceVectorX, y: refBlockY + faceVectorY, z: refBlockZ + faceVectorZ};
        console.log(`JS: Successfully placed ${itemName} near (${refBlockX},${refBlockY},${refBlockZ}) for operationId ${operationId}. Placed at: ${JSON.stringify(placedLocation)}`);
        if (global.python) {
          global.python.emit('mineflayerTaskComplete', {
            operationId,
            status: "success",
            message: `Placed ${itemName}.`,
            placed_location: placedLocation
          });
        }
      })
      .catch((err) => {
        console.error(`JS: Placing block ${itemName} failed for operationId ${operationId}: ${err.message}`);
        if (global.python) {
          global.python.emit('mineflayerTaskComplete', {
            operationId,
            status: "error",
            message: `Placing block failed: ${err.message}`
          });
        }
      });

    return { status: "pending", operationId: operationId, message: `Placing of ${itemName} initiated.` };
}

module.exports = {
  initializeBot,
  goToXYZ,
  findBlock,
  mineBlock,
  getInventory,
  craftItem,
  placeBlock
};
